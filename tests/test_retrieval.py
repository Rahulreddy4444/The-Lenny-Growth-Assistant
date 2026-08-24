"""
Tests for retrieval service — vector search correctness and metadata.
"""

import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestChunker:
    """Test the transcript chunker on real data."""

    def test_discover_transcripts(self):
        """Should discover transcript files in the episodes directory."""
        from ingestion.chunker import discover_transcripts
        from pathlib import Path

        repo_path = Path(__file__).parent.parent / "ingestion" / "lennys-podcast-transcripts"
        if not repo_path.exists():
            pytest.skip("Transcript repo not cloned")

        transcripts = discover_transcripts(repo_path)
        assert len(transcripts) > 0, "Should find at least one transcript"
        assert all(t.name == "transcript.md" for t in transcripts), "All should be transcript.md files"

    def test_process_transcript_metadata(self):
        """Should extract correct metadata from YAML frontmatter."""
        from ingestion.chunker import discover_transcripts, process_transcript
        from pathlib import Path

        repo_path = Path(__file__).parent.parent / "ingestion" / "lennys-podcast-transcripts"
        if not repo_path.exists():
            pytest.skip("Transcript repo not cloned")

        transcripts = discover_transcripts(repo_path)
        chunks = process_transcript(transcripts[0])

        assert len(chunks) > 0, "Should produce at least one chunk"

        first_chunk = chunks[0]
        assert first_chunk.metadata.episode_title, "Should have episode title"
        assert first_chunk.metadata.guest, "Should have guest name"
        assert first_chunk.metadata.youtube_url, "Should have YouTube URL"
        assert first_chunk.chunk_hash, "Should have a hash"
        assert first_chunk.content, "Should have content"

    def test_chunk_has_content_and_hash(self):
        """Each chunk should have non-empty content and a unique hash."""
        from ingestion.chunker import discover_transcripts, process_transcript
        from pathlib import Path

        repo_path = Path(__file__).parent.parent / "ingestion" / "lennys-podcast-transcripts"
        if not repo_path.exists():
            pytest.skip("Transcript repo not cloned")

        transcripts = discover_transcripts(repo_path)
        chunks = process_transcript(transcripts[0])

        hashes = set()
        for chunk in chunks:
            assert chunk.content.strip(), "Chunk content should not be empty"
            assert chunk.chunk_hash, "Chunk should have a hash"
            hashes.add(chunk.chunk_hash)

        assert len(hashes) == len(chunks), "All chunk hashes should be unique"

    def test_idempotent_hashing(self):
        """Processing the same transcript twice should produce the same hashes."""
        from ingestion.chunker import discover_transcripts, process_transcript
        from pathlib import Path

        repo_path = Path(__file__).parent.parent / "ingestion" / "lennys-podcast-transcripts"
        if not repo_path.exists():
            pytest.skip("Transcript repo not cloned")

        transcripts = discover_transcripts(repo_path)
        chunks_1 = process_transcript(transcripts[0])
        chunks_2 = process_transcript(transcripts[0])

        assert len(chunks_1) == len(chunks_2), "Should produce same number of chunks"
        for c1, c2 in zip(chunks_1, chunks_2):
            assert c1.chunk_hash == c2.chunk_hash, "Hashes should be identical"
