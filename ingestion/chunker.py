"""
Transcript chunker for Lenny's Podcast transcripts.

Parses YAML-frontmatter Markdown files from the episodes/ directory structure
and produces chunks with source metadata attached.

Actual repo structure (discovered):
  episodes/{guest-name}/transcript.md
  Each file has YAML frontmatter with: guest, title, youtube_url, video_id,
  publish_date, description, duration_seconds, duration, view_count, channel, keywords
  Content has speaker-attributed sections with timestamps like:
    Speaker Name (HH:MM:SS):
"""

import hashlib
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ChunkMetadata:
    episode_title: str
    guest: str
    publish_date: str
    youtube_url: str
    video_id: str
    section_speaker: Optional[str] = None
    section_timestamp: Optional[str] = None
    chunk_index: int = 0
    keywords: list[str] = field(default_factory=list)


@dataclass
class TranscriptChunk:
    content: str
    metadata: ChunkMetadata
    chunk_hash: str = ""

    def __post_init__(self):
        if not self.chunk_hash:
            self.chunk_hash = hashlib.sha256(
                f"{self.metadata.episode_title}:{self.metadata.chunk_index}:{self.content[:200]}".encode()
            ).hexdigest()


def parse_transcript_file(filepath: Path) -> tuple[dict, str]:
    """Parse a transcript.md file into frontmatter dict and transcript text."""
    content = filepath.read_text(encoding="utf-8")

    # Split YAML frontmatter
    parts = content.split("---", 2)
    if len(parts) >= 3:
        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            frontmatter = {}
        transcript = parts[2].strip()
    else:
        frontmatter = {}
        transcript = content.strip()

    return frontmatter or {}, transcript


def extract_speaker_sections(transcript: str) -> list[dict]:
    """Extract speaker-attributed sections from transcript text.

    Matches patterns like:
      Speaker Name (HH:MM:SS):
      (HH:MM:SS):
    """
    # Pattern matches "Speaker Name (timestamp):" or just "(timestamp):"
    pattern = r'^(?:([A-Za-z][A-Za-z\s\.\-\']+?)\s*)?\((\d{1,2}:\d{2}:\d{2})\):?\s*$'

    sections = []
    current_speaker = None
    current_timestamp = None
    current_text_lines = []

    for line in transcript.split("\n"):
        # Skip markdown headers
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        match = re.match(pattern, stripped)
        if match:
            # Save previous section if exists
            if current_text_lines:
                text = " ".join(current_text_lines).strip()
                if text:
                    sections.append({
                        "speaker": current_speaker,
                        "timestamp": current_timestamp,
                        "text": text,
                    })

            # Start new section
            current_speaker = match.group(1) or current_speaker  # Carry forward speaker
            current_timestamp = match.group(2)
            current_text_lines = []
        else:
            if stripped:
                current_text_lines.append(stripped)

    # Don't forget the last section
    if current_text_lines:
        text = " ".join(current_text_lines).strip()
        if text:
            sections.append({
                "speaker": current_speaker,
                "timestamp": current_timestamp,
                "text": text,
            })

    return sections


def chunk_sections(
    sections: list[dict],
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[dict]:
    """Merge speaker sections into chunks of approximately max_tokens words.

    Uses word count as a proxy for tokens (close enough for chunking).
    Includes overlap between chunks for context continuity.
    """
    if not sections:
        return []

    chunks = []
    current_chunk_texts = []
    current_chunk_word_count = 0
    current_chunk_first_speaker = None
    current_chunk_first_timestamp = None

    for section in sections:
        text = section["text"]
        word_count = len(text.split())

        if current_chunk_word_count == 0:
            # Start a new chunk
            current_chunk_first_speaker = section["speaker"]
            current_chunk_first_timestamp = section["timestamp"]

        if current_chunk_word_count + word_count > max_tokens and current_chunk_texts:
            # Emit current chunk
            chunks.append({
                "text": "\n\n".join(current_chunk_texts),
                "speaker": current_chunk_first_speaker,
                "timestamp": current_chunk_first_timestamp,
            })

            # Start new chunk with overlap from end of previous
            overlap_text = text[:overlap_tokens * 5]  # rough char estimate
            current_chunk_texts = [overlap_text] if overlap_tokens > 0 else []
            current_chunk_word_count = len(overlap_text.split()) if overlap_tokens > 0 else 0
            current_chunk_first_speaker = section["speaker"]
            current_chunk_first_timestamp = section["timestamp"]

        current_chunk_texts.append(text)
        current_chunk_word_count += word_count

    # Emit last chunk
    if current_chunk_texts:
        chunks.append({
            "text": "\n\n".join(current_chunk_texts),
            "speaker": current_chunk_first_speaker,
            "timestamp": current_chunk_first_timestamp,
        })

    return chunks


def process_transcript(filepath: Path) -> list[TranscriptChunk]:
    """Process a single transcript file into chunks with metadata."""
    frontmatter, transcript_text = parse_transcript_file(filepath)

    if not transcript_text:
        return []

    # Extract metadata from frontmatter
    guest = frontmatter.get("guest", filepath.parent.name.replace("-", " ").title())
    title = frontmatter.get("title", f"Episode with {guest}")
    youtube_url = frontmatter.get("youtube_url", "")
    video_id = frontmatter.get("video_id", "")
    publish_date = str(frontmatter.get("publish_date", ""))
    keywords = frontmatter.get("keywords", [])

    # Extract speaker sections
    sections = extract_speaker_sections(transcript_text)

    # If no speaker sections found, fall back to paragraph chunking
    if not sections:
        paragraphs = [p.strip() for p in transcript_text.split("\n\n") if p.strip()]
        sections = [{"speaker": guest, "timestamp": None, "text": p} for p in paragraphs]

    # Chunk the sections
    raw_chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=50)

    # Build TranscriptChunk objects
    result = []
    for i, chunk_data in enumerate(raw_chunks):
        metadata = ChunkMetadata(
            episode_title=title,
            guest=guest,
            publish_date=publish_date,
            youtube_url=youtube_url,
            video_id=video_id,
            section_speaker=chunk_data.get("speaker"),
            section_timestamp=chunk_data.get("timestamp"),
            chunk_index=i,
            keywords=keywords,
        )
        result.append(TranscriptChunk(content=chunk_data["text"], metadata=metadata))

    return result


def discover_transcripts(repo_path: Path) -> list[Path]:
    """Discover all transcript.md files in the episodes/ directory."""
    episodes_dir = repo_path / "episodes"
    if not episodes_dir.exists():
        raise FileNotFoundError(f"Episodes directory not found: {episodes_dir}")

    transcripts = sorted(episodes_dir.glob("*/transcript.md"))
    return transcripts
