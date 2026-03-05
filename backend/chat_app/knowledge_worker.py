from __future__ import annotations

import asyncio
import os
from pathlib import Path

from database.connections import (
    RAGDBConnection,
    claim_next_knowledge_job,
    ensure_knowledge_tables,
    finish_knowledge_job,
    update_knowledge_job,
)
from core.gen_ai_provider import GenAIEmbedProvider


async def run_knowledge_worker(stop_event: asyncio.Event, poll_seconds: float = 2.0) -> None:
    """Background worker that consumes queued knowledge jobs and writes embeddings."""

    db = RAGDBConnection()
    embedder = GenAIEmbedProvider()

    knowledge_root = Path(__file__).resolve().parents[1] / "knowledge"

    while not stop_event.is_set():
        job = None
        try:
            with db.get_connection() as conn:
                ensure_knowledge_tables(conn, db.table_prefix)
                job = claim_next_knowledge_job(conn, db.table_prefix)

            if not job:
                await asyncio.sleep(poll_seconds)
                continue

            job_id = int(job["id"])
            storage_path = str(job["storage_path"])
            pdf_path = (knowledge_root / storage_path).resolve()

            if not pdf_path.exists():
                with db.get_connection() as conn:
                    finish_knowledge_job(conn, db.table_prefix, job_id, ok=False, message="file not found")
                continue

            with db.get_connection() as conn:
                update_knowledge_job(conn, db.table_prefix, job_id, progress_pct=5, message="loading PDF")

            # Run CPU/network heavy embedding work in a thread so we don't block the event loop.
            def _embed_and_insert() -> None:
                embedder.load_and_insert_pdf(str(pdf_path), db)

            await asyncio.to_thread(_embed_and_insert)

            with db.get_connection() as conn:
                finish_knowledge_job(conn, db.table_prefix, job_id, ok=True, message="embedded and stored")

        except Exception as e:
            if job and "id" in job:
                try:
                    with db.get_connection() as conn:
                        finish_knowledge_job(conn, db.table_prefix, int(job["id"]), ok=False, message=str(e))
                except Exception:
                    pass
            await asyncio.sleep(poll_seconds)
