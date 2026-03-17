from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from database.connections import (
    RAGDBConnection,
    claim_next_knowledge_job,
    ensure_knowledge_tables,
    finish_knowledge_job,
    get_knowledge_job,
    update_knowledge_job,
)
from core.gen_ai_provider import GenAIEmbedProvider

logger = logging.getLogger(__name__)
PROGRESS_THROTTLE_SECONDS = float(os.getenv("KNOWLEDGE_PROGRESS_THROTTLE_SECONDS", "1.0"))
PROGRESS_MIN_DELTA = int(os.getenv("KNOWLEDGE_PROGRESS_MIN_DELTA", "2"))


async def run_knowledge_worker(stop_event: asyncio.Event, poll_seconds: float = 2.0) -> None:
    """Background worker that consumes queued knowledge jobs and writes embeddings."""

    logger.info("Knowledge worker started")
    db = RAGDBConnection()
    embedder = GenAIEmbedProvider()

    knowledge_root = Path(__file__).resolve().parents[1] / "knowledge"
    logger.info(f"Knowledge root: {knowledge_root}")

    while not stop_event.is_set():
        job = None
        try:
            with db.get_connection() as conn:
                ensure_knowledge_tables(conn, db.table_prefix)
                job = claim_next_knowledge_job(conn, db.table_prefix)

            if not job:
                logger.debug("No queued jobs found, sleeping 2s...")
                await asyncio.sleep(poll_seconds)
                continue

            job_id = int(job["id"])
            files = list(job.get("files") or [])
            logger.info(f"Claimed job #{job_id} with {len(files)} file(s)")

            if not files:
                # Race-condition guard: uploads create the job first, then link files.
                # The worker can claim the job in between those steps.
                logger.warning(
                    f"Job #{job_id} has no files yet; waiting briefly for uploads to attach files"
                )

                max_wait_seconds = float(os.getenv("KNOWLEDGE_JOB_WAIT_FOR_FILES_SECONDS", "10"))
                waited = 0.0
                refreshed_files: list[dict] = []
                while waited < max_wait_seconds and not stop_event.is_set():
                    await asyncio.sleep(1.0)
                    waited += 1.0
                    try:
                        with db.get_connection() as conn:
                            ensure_knowledge_tables(conn, db.table_prefix)
                            refreshed = get_knowledge_job(conn, db.table_prefix, job_id)
                        if refreshed:
                            refreshed_files = list(refreshed.get("files") or [])
                            if refreshed_files:
                                break
                    except Exception as refresh_err:
                        logger.debug("Job #%s refresh failed: %s", job_id, str(refresh_err))

                if refreshed_files:
                    files = refreshed_files
                    logger.info(f"Job #{job_id} now has {len(files)} file(s) after waiting")
                else:
                    # If files still aren't attached, release back to queue so the uploader can finish.
                    with db.get_connection() as conn:
                        update_knowledge_job(
                            conn,
                            db.table_prefix,
                            job_id,
                            status="queued",
                            message="waiting for files to be attached",
                        )
                    await asyncio.sleep(poll_seconds)
                    continue

            with db.get_connection() as conn:
                update_knowledge_job(conn, db.table_prefix, job_id, progress_pct=1, message=f"batch started ({len(files)} file(s))")

            # Process each PDF in the batch.
            for idx, f in enumerate(files, start=1):
                storage_path = str(f.get("storage_path") or "")
                filename = str(f.get("filename") or storage_path)
                pdf_path = (knowledge_root / storage_path).resolve()
                logger.info(f"[{idx}/{len(files)}] Processing {filename} at {pdf_path}")
                
                if not pdf_path.exists():
                    logger.warning(f"[{idx}/{len(files)}] File not found: {pdf_path}")
                    with db.get_connection() as conn:
                        update_knowledge_job(conn, db.table_prefix, job_id, message=f"missing: {filename}")
                    continue

                # Map file index to progress band [5..95]
                base_pct = 5 + int(((idx - 1) / max(1, len(files))) * 90)
                file_pct_range = 90 / max(1, len(files))
                
                logger.info(f"[{idx}/{len(files)}] Starting embedding for {filename}, base progress={base_pct}%")
                with db.get_connection() as conn:
                    update_knowledge_job(conn, db.table_prefix, job_id, progress_pct=base_pct, message=f"[{idx}/{len(files)}] starting {filename}")

                progress_state = {
                    "last_pct": base_pct,
                    "last_write_time": time.monotonic(),
                    "pending_pct": base_pct,
                    "pending_message": f"[{idx}/{len(files)}] starting {filename}",
                }

                def flush_progress(force: bool = False):
                    pending_pct = int(progress_state["pending_pct"])
                    pending_message = str(progress_state["pending_message"])
                    now = time.monotonic()
                    pct_delta = abs(pending_pct - int(progress_state["last_pct"]))
                    elapsed = now - float(progress_state["last_write_time"])
                    if not force and pct_delta < PROGRESS_MIN_DELTA and elapsed < PROGRESS_THROTTLE_SECONDS:
                        return
                    with db.get_connection() as conn:
                        update_knowledge_job(
                            conn,
                            db.table_prefix,
                            job_id,
                            progress_pct=pending_pct,
                            message=pending_message,
                        )
                    progress_state["last_pct"] = pending_pct
                    progress_state["last_write_time"] = now

                def progress_callback(stage: str, sub_pct: int, msg: str):
                    file_progress = base_pct + int((sub_pct / 100.0) * file_pct_range)
                    file_progress = min(95, max(base_pct, file_progress))
                    progress_state["pending_pct"] = file_progress
                    progress_state["pending_message"] = f"[{idx}/{len(files)}] {filename}: {stage} - {msg}"
                    flush_progress()

                def _embed_one() -> None:
                    logger.info(f"[{idx}/{len(files)}] Calling load_and_insert_pdf_with_progress for {pdf_path}")
                    try:
                        embedder.load_and_insert_pdf_with_progress(
                            str(pdf_path),
                            db,
                            progress_callback=progress_callback
                        )
                        logger.info(f"[{idx}/{len(files)}] Successfully embedded {filename}")
                    except Exception as e:
                        logger.exception(f"[{idx}/{len(files)}] Error during embedding: {e}")
                        raise

                try:
                    await asyncio.to_thread(_embed_one)
                    flush_progress(force=True)
                except Exception as e:
                    logger.error(f"[{idx}/{len(files)}] Failed to embed {filename}: {e}")
                    with db.get_connection() as conn:
                        update_knowledge_job(conn, db.table_prefix, job_id, message=f"error: {filename}: {str(e)[:100]}")
                    continue

                with db.get_connection() as conn:
                    pct = 5 + int((idx / max(1, len(files))) * 90)
                    logger.info(f"[{idx}/{len(files)}] Done with {filename}, progress={pct}%")
                    update_knowledge_job(conn, db.table_prefix, job_id, progress_pct=pct, message=f"[{idx}/{len(files)}] completed {filename}")

            logger.info(f"Job #{job_id} completed successfully")
            with db.get_connection() as conn:
                finish_knowledge_job(conn, db.table_prefix, job_id, ok=True, message="batch completed")

        except Exception as e:
            logger.exception(f"Worker error: {e}")
            if job and "id" in job:
                try:
                    with db.get_connection() as conn:
                        finish_knowledge_job(conn, db.table_prefix, int(job["id"]), ok=False, message=str(e)[:500])
                except Exception as db_err:
                    logger.exception(f"Failed to mark job as failed: {db_err}")
            await asyncio.sleep(poll_seconds)
            await asyncio.sleep(poll_seconds)
