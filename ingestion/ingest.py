"""
Ingestion script for Lenny's Podcast transcripts.

Usage:
    python -m ingestion.ingest [--repo-path PATH] [--reset]

Discovers transcript files, chunks them, embeds via Ollama nomic-embed-text,
and upserts into PostgreSQL with pgvector. Idempotent via chunk_hash dedup.
"""

import argparse
import hashlib
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
import requests
from dotenv import load_dotenv

load_dotenv()

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from ingestion.chunker import discover_transcripts, process_transcript

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL_SYNC", "postgresql://postgres:postgres@localhost:5432/lenny")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBEDDING_DIM = 768
BATCH_SIZE = 20  # Number of chunks to embed in one request


def ensure_db_schema(conn):
    """Create the pgvector extension and transcript_chunks table if not exists."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS transcript_chunks (
                id SERIAL PRIMARY KEY,
                chunk_hash TEXT UNIQUE NOT NULL,
                episode_title TEXT NOT NULL,
                guest TEXT,
                publish_date TEXT,
                youtube_url TEXT,
                video_id TEXT,
                section_speaker TEXT,
                section_timestamp TEXT,
                chunk_index INTEGER,
                keywords TEXT[],
                content TEXT NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        # Create HNSW index for cosine similarity search
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
            ON transcript_chunks
            USING hnsw (embedding vector_cosine_ops);
        """)
        conn.commit()
    logger.info("Database schema ensured.")


def get_existing_hashes(conn) -> set:
    """Get all existing chunk hashes for idempotency."""
    with conn.cursor() as cur:
        cur.execute("SELECT chunk_hash FROM transcript_chunks;")
        return {row[0] for row in cur.fetchall()}


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using Ollama nomic-embed-text."""
    url = f"{OLLAMA_BASE_URL}/api/embed"
    payload = {
        "model": OLLAMA_EMBED_MODEL,
        "input": texts,
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. Is Ollama running?")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(f"Ollama embedding error: {e}")
        logger.error(f"Response: {response.text}")
        raise


def insert_chunks(conn, chunks_with_embeddings: list[tuple]):
    """Bulk insert chunks with embeddings into the database."""
    with conn.cursor() as cur:
        sql = """
            INSERT INTO transcript_chunks
                (chunk_hash, episode_title, guest, publish_date, youtube_url,
                 video_id, section_speaker, section_timestamp, chunk_index,
                 keywords, content, embedding)
            VALUES %s
            ON CONFLICT (chunk_hash) DO NOTHING;
        """
        execute_values(cur, sql, chunks_with_embeddings)
        conn.commit()


def run_ingestion(repo_path: Path, reset: bool = False):
    """Main ingestion pipeline."""
    logger.info(f"Starting ingestion from: {repo_path}")

    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Connected to database.")
    except psycopg2.OperationalError as e:
        logger.error(f"Cannot connect to database: {e}")
        logger.error(f"DATABASE_URL_SYNC: {DATABASE_URL.split('@')[0]}@***")
        sys.exit(1)

    # Reset if requested
    if reset:
        logger.warning("Resetting transcript_chunks table...")
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS transcript_chunks;")
            conn.commit()

    # Ensure schema
    ensure_db_schema(conn)

    # Get existing hashes for idempotency
    existing_hashes = get_existing_hashes(conn)
    logger.info(f"Found {len(existing_hashes)} existing chunks in database.")

    # Discover transcripts
    transcripts = discover_transcripts(repo_path)
    logger.info(f"Discovered {len(transcripts)} transcript files.")

    # Process each transcript
    total_chunks = 0
    new_chunks = 0
    skipped_chunks = 0

    for i, transcript_path in enumerate(transcripts):
        guest_dir = transcript_path.parent.name
        logger.info(f"[{i+1}/{len(transcripts)}] Processing: {guest_dir}")

        chunks = process_transcript(transcript_path)
        total_chunks += len(chunks)

        # Filter out already-ingested chunks
        new = [c for c in chunks if c.chunk_hash not in existing_hashes]
        skipped = len(chunks) - len(new)
        skipped_chunks += skipped

        if not new:
            logger.debug(f"  Skipped {skipped} existing chunks.")
            continue

        # Embed in batches
        for batch_start in range(0, len(new), BATCH_SIZE):
            batch = new[batch_start:batch_start + BATCH_SIZE]
            texts = [c.content for c in batch]

            try:
                embeddings = embed_texts(texts)
            except Exception as e:
                logger.error(f"  Failed to embed batch: {e}")
                continue

            # Prepare rows for insert
            rows = []
            for chunk, embedding in zip(batch, embeddings):
                m = chunk.metadata
                rows.append((
                    chunk.chunk_hash,
                    m.episode_title,
                    m.guest,
                    m.publish_date,
                    m.youtube_url,
                    m.video_id,
                    m.section_speaker,
                    m.section_timestamp,
                    m.chunk_index,
                    m.keywords,
                    chunk.content,
                    str(embedding),  # pgvector accepts string representation
                ))

            insert_chunks(conn, rows)
            new_chunks += len(rows)

            # Add to existing hashes set
            for chunk in batch:
                existing_hashes.add(chunk.chunk_hash)

        logger.info(f"  Inserted {len(new)} new chunks, skipped {skipped}.")

    conn.close()
    logger.info(
        f"Ingestion complete. "
        f"Total: {total_chunks}, New: {new_chunks}, Skipped: {skipped_chunks}"
    )


def clone_or_update_repo(target_path: Path):
    """Clone or pull the transcript repository."""
    repo_url = "https://github.com/ChatPRD/lennys-podcast-transcripts.git"

    if (target_path / ".git").exists():
        logger.info("Transcript repo exists, pulling latest...")
        subprocess.run(
            ["git", "pull"],
            cwd=str(target_path),
            check=True,
            capture_output=True,
        )
    else:
        logger.info("Cloning transcript repo...")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", repo_url, str(target_path), "--depth", "1"],
            check=True,
            capture_output=True,
        )
    logger.info("Transcript repo ready.")


def main():
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path(__file__).parent / "lennys-podcast-transcripts",
        help="Path to the transcript repository",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate the transcript_chunks table",
    )
    parser.add_argument(
        "--skip-clone",
        action="store_true",
        help="Skip cloning/pulling the transcript repo",
    )
    args = parser.parse_args()

    if not args.skip_clone:
        clone_or_update_repo(args.repo_path)

    run_ingestion(args.repo_path, reset=args.reset)


if __name__ == "__main__":
    main()
