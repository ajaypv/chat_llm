import logging
import os
import re
from pathlib import Path
import asyncio

import click
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from starlette.responses import StreamingResponse

from chat_app.main_llm import OCIOutageEnergyLLM
from database.connections import RAGDBConnection, ensure_knowledge_tables, create_knowledge_file, create_knowledge_job, add_file_to_job, get_knowledge_job
from chat_app.knowledge_worker import run_knowledge_worker

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_app() -> FastAPI:
    app = FastAPI(title="chat_llm backend", version="0.1.0")

    stop_event = asyncio.Event()
    worker_task: asyncio.Task | None = None

    @app.on_event("startup")
    async def _startup_worker():
        nonlocal worker_task
        # Run a single in-process worker for development.
        worker_task = asyncio.create_task(run_knowledge_worker(stop_event))

    @app.on_event("shutdown")
    async def _shutdown_worker():
        stop_event.set()
        if worker_task is not None:
            try:
                await worker_task
            except Exception:
                pass

    upload_root = (Path(__file__).resolve().parent / "knowledge")

    def _safe_category(value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise HTTPException(status_code=400, detail="category is required")
        if len(value) > 64:
            raise HTTPException(status_code=400, detail="category too long")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise HTTPException(
                status_code=400,
                detail="category must match [A-Za-z0-9_-]+",
            )
        return value

    def _safe_filename(name: str) -> str:
        base = os.path.basename(name or "")
        base = base.replace("\x00", "").strip()
        if not base:
            return "upload.pdf"
        return base

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    llm = OCIOutageEnergyLLM()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(payload: dict):
        # keeping simple JSON input: {"query": "...", "session_id": "..."}
        query = (payload.get("query") or "").strip()
        if not query:
            return {"error": "query is required"}

        request_id = payload.get("request_id") or str(uuid4())

        categories = payload.get("categories")
        if categories is None:
            categories_list: list[str] = []
        elif isinstance(categories, list):
            categories_list = [
                str(c).strip().lower() for c in categories if str(c).strip()
            ]
        else:
            categories_list = [str(categories).strip().lower()] if str(categories).strip() else []

        session_id = payload.get("session_id") or "local"
        top_k = int(payload.get("top_k") or 10)

        logger.info(
            "[rid=%s] /chat: session_id=%s query_len=%s top_k=%s categories=%s",
            request_id,
            session_id,
            len(query),
            top_k,
            categories_list,
        )

        # Always run RAG retrieval server-side so the experience doesn't depend on
        # whether the model decides to invoke tools.
        rag_context: str = ""
        rag_debug_updates: list[str] = []
        try:
            from chat_app.rag_tool import semantic_search_raw
            import json

            # Emit a tool-like status line so the frontend can render it in the Tool UI.
            rag_debug_updates.append(
                "Model calling tool: semantic_search with args "
                + json.dumps({"query": query, "top_k": top_k, "categories": categories_list})
            )

            rag_context = await semantic_search_raw(
                query=query,
                top_k=top_k,
                categories=categories_list,
                request_id=request_id,
            )

            rag_debug_updates.append(
                "Tool semantic_search responded with:\n" + str(rag_context)
            )
        except Exception as e:
            logger.warning("[rid=%s] semantic_search failed: %s", request_id, str(e))

        logger.info(
            "[rid=%s] /chat: rag_context_present=%s",
            request_id,
            bool(rag_context and "No relevant documents found" not in rag_context),
        )

        async def gen():
            import json

            # Send RAG tool-call/result updates first so the UI shows them
            # even if the LLM stream is slow.
            for u in rag_debug_updates:
                yield json.dumps({"updates": u}) + "\n"

            # Stream chunks as NDJSON so the frontend can update incrementally.
            augmented = query
            selected_cats = categories_list
            if rag_context:
                augmented = (
                    "You are answering a user question using retrieved knowledge snippets.\n"
                    "Follow these rules:\n"
                    "- Treat the retrieved context as the primary source of truth.\n"
                    "- If Selected knowledge categories is non-empty, only rely on information that fits those categories.\n"
                    "- Do not say 'no relevant context found' because context IS provided below.\n"
                    "- If the context does not contain the answer, say what is missing and ask a brief clarifying question.\n\n"
                    f"Selected knowledge categories: {selected_cats if selected_cats else '[]'}\n\n"
                    f"Retrieved context (each snippet includes a Source):\n{rag_context}\n\n"
                    f"User question:\n{query}\n\n"
                    "Answer:\n"
                )
            else:
                augmented = (
                    "No retrieved knowledge context was found for this query.\n"
                    f"Selected knowledge categories: {selected_cats if selected_cats else '[]'}\n\n"
                    f"User question:\n{query}\n\n"
                    "Answer using general knowledge if appropriate, and clearly state that no retrieved context was available.\n"
                )

            async for chunk in llm.oci_stream(augmented, session_id=session_id, categories=categories_list):
                yield json.dumps(chunk) + "\n"

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    @app.post("/knowledge/upload")
    async def knowledge_upload(
        category: str = Form(...),
        files: list[UploadFile] = File(...),
    ):
        cat = _safe_category(category)
        dest_dir = (upload_root / cat).resolve()

        # Ensure uploads stay within backend folder.
        if upload_root not in dest_dir.parents and dest_dir != upload_root:
            raise HTTPException(status_code=400, detail="invalid category")

        dest_dir.mkdir(parents=True, exist_ok=True)

        db = RAGDBConnection()
        batch_job_id: int | None = None
        saved: list[dict[str, str]] = []

        # Create a single batch job for the whole upload.
        try:
            with db.get_connection() as conn:
                ensure_knowledge_tables(conn, db.table_prefix)
                batch_job_id = create_knowledge_job(conn, db.table_prefix)
        except Exception as e:
            logger.warning("Failed to create batch knowledge job: %s", str(e))
        for f in files:
            if not f.filename:
                continue
            filename = _safe_filename(f.filename)
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="only PDF files are allowed")
            content_type = (f.content_type or "").lower()
            if content_type not in ("application/pdf", "application/octet-stream", ""):
                raise HTTPException(status_code=400, detail="only PDF files are allowed")

            target = dest_dir / filename
            # Avoid accidental overwrite by appending a counter.
            if target.exists():
                stem = target.stem
                suffix = target.suffix
                i = 1
                while True:
                    candidate = dest_dir / f"{stem}_{i}{suffix}"
                    if not candidate.exists():
                        target = candidate
                        break
                    i += 1

            data = await f.read()
            if not data:
                raise HTTPException(status_code=400, detail=f"empty file: {filename}")
            target.write_bytes(data)
            logger.info(f"Saved file to disk: {target}")

            # Enqueue an embedding job in DB.
            try:
                with db.get_connection() as conn:
                    ensure_knowledge_tables(conn, db.table_prefix)
                    logger.info(f"Creating knowledge_file record for {target.name}")
                    file_id = create_knowledge_file(
                        conn,
                        db.table_prefix,
                        category=cat,
                        filename=target.name,
                        storage_path=str(target.relative_to(upload_root)).replace("\\", "/"),
                        size_bytes=len(data),
                    )
                    logger.info(f"Created knowledge_file #{file_id}")
                    if batch_job_id is not None:
                        logger.info(f"Adding file #{file_id} to job #{batch_job_id}")
                        add_file_to_job(conn, db.table_prefix, job_id=batch_job_id, file_id=file_id)
                        logger.info(f"Successfully linked file #{file_id} to job #{batch_job_id}")
                    else:
                        logger.warning(f"No batch_job_id, skipping add_file_to_job for {target.name}")
            except Exception as e:
                # If DB isn't configured, still succeed storing file.
                logger.exception(f"Failed to enqueue knowledge job for {target.name}: %s", str(e))

            saved.append(
                {
                    "filename": target.name,
                    "category": cat,
                    "path": str(target.relative_to(upload_root)).replace("\\", "/"),
                }
            )

        return {"ok": True, "saved": saved, "job_id": batch_job_id}

    @app.get("/knowledge/jobs/{job_id}")
    async def knowledge_job_status(job_id: int):
        db = RAGDBConnection()
        with db.get_connection() as conn:
            ensure_knowledge_tables(conn, db.table_prefix)
            job = get_knowledge_job(conn, db.table_prefix, job_id=job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.get("/knowledge/list")
    async def knowledge_list(category: str | None = None):
        root = upload_root
        root.mkdir(parents=True, exist_ok=True)

        def _rel(p: Path) -> str:
            return str(p.relative_to(root)).replace("\\", "/")

        if category:
            cat = _safe_category(category)
            cat_dir = (root / cat)
            if not cat_dir.exists():
                return {"category": cat, "files": []}
            files = sorted([p for p in cat_dir.glob("*.pdf") if p.is_file()])
            return {
                "category": cat,
                "files": [{"filename": p.name, "path": _rel(p), "bytes": p.stat().st_size} for p in files],
            }

        categories: list[dict] = []
        for d in sorted([p for p in root.iterdir() if p.is_dir()]):
            pdfs = sorted([p for p in d.glob("*.pdf") if p.is_file()])
            categories.append(
                {
                    "category": d.name,
                    "count": len(pdfs),
                }
            )
        return {"categories": categories}

    @app.get("/knowledge/categories")
    async def knowledge_categories():
        """Return available knowledge categories from DB (preferred) with a filesystem fallback."""
        db = RAGDBConnection()
        try:
            with db.get_connection() as conn:
                ensure_knowledge_tables(conn, db.table_prefix)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT DISTINCT category
                        FROM {db.table_prefix}_knowledge_file
                        ORDER BY category
                        """
                    )
                    cats = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None]
            return {"categories": cats}
        except Exception:
            # If DB isn't reachable, fall back to folders.
            root = upload_root
            root.mkdir(parents=True, exist_ok=True)
            cats = [p.name for p in sorted([p for p in root.iterdir() if p.is_dir()])]
            return {"categories": cats}

    async def _chat_stream(query: str, session_id: str):
        async def gen():
            async for chunk in llm.oci_stream(query, session_id=session_id):
                # send JSON per event; frontend parses `evt.data`
                import json
                yield f"data: {json.dumps(chunk)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    # Provide both route spellings to avoid 404s from older frontend builds
    @app.get("/chat/stream")
    async def chat_stream(query: str, session_id: str = "local"):
        return await _chat_stream(query=query, session_id=session_id)

    @app.get("/chat-stream")
    async def chat_stream_dash(query: str, session_id: str = "local"):
        return await _chat_stream(query=query, session_id=session_id)

    return app


@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000, type=int)
def main(host: str, port: int):
    app = build_app()
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
