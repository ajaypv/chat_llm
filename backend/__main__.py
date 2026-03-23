import logging
import os
import re
import shutil
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager

import click
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from starlette.responses import StreamingResponse
from langchain.messages import HumanMessage

from chat_app.main_llm import KnowledgeAssistantAgent, stream_augmented_response
from chat_app.model_registry import (
    DEFAULT_CHAT_MODEL,
    SUPPORTED_CHAT_MODELS,
    is_supported_chat_model,
)
from database.connections import RAGDBConnection, ensure_knowledge_tables, create_knowledge_delete_job, create_knowledge_file, create_knowledge_job, add_file_to_job, get_knowledge_delete_job, get_knowledge_job, update_knowledge_job, finish_knowledge_job
from chat_app.knowledge_worker import run_knowledge_worker
from langchain_oci import ChatOCIOpenAI
from langchain_oci.common.auth import OCIAuthType, create_oci_client_kwargs

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _should_use_semantic_search(query: str, categories: list[str]) -> bool:
    text = str(query or "").strip()
    if not text:
        return False

    if categories:
        return True

    lowered = text.lower()
    short_chat_inputs = {
        "hi",
        "hey",
        "hello",
        "hey hi",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "ok",
        "okay",
    }
    if lowered in short_chat_inputs:
        return False

    retrieval_signals = (
        "based on",
        "from the knowledge base",
        "from the docs",
        "from the document",
        "in the document",
        "in the docs",
        "according to",
        "knowledge base",
        "search the docs",
        "search knowledge",
        "find in",
        "look up",
        "what does the document say",
        "restaurant",
        "restaurants",
        "menu",
        "menus",
        "dish",
        "dishes",
        "cuisine",
        "review",
        "reviews",
        "nutrition",
        "healthy",
        "food",
    )
    return any(signal in lowered for signal in retrieval_signals)


def _build_oci_web_search_client() -> ChatOCIOpenAI:
    if not os.getenv("OCI_OPENAI_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "Web search requires an OCI OpenAI API key, but neither OCI_OPENAI_API_KEY nor OPENAI_API_KEY is configured. "
            "The current SERVICE_ENDPOINT/AUTH_PROFILE setup is sufficient for ChatOCIGenAI, but this OpenAI-compatible web search path in your tenancy is rejecting signer-only auth."
        )

    client_kwargs = create_oci_client_kwargs(
        auth_type=OCIAuthType.API_KEY.name,
        service_endpoint=os.getenv("SERVICE_ENDPOINT"),
        auth_profile=os.getenv("AUTH_PROFILE", "DEFAULT"),
    )
    return ChatOCIOpenAI(
        auth=client_kwargs.get("signer"),
        model=os.getenv("OCI_OPENAI_WEB_SEARCH_MODEL", "openai.gpt-4.1"),
        service_endpoint=os.getenv("SERVICE_ENDPOINT"),
        compartment_id=os.getenv("COMPARTMENT_ID"),
        store=False,
    )


def _extract_web_search_payload(ai_message) -> tuple[str, list[dict[str, str]]]:
    output_text = ""
    sources: list[dict[str, str]] = []

    content = getattr(ai_message, "content", None)
    if isinstance(content, str):
        output_text = content
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"text", "output_text"}:
                output_text += str(item.get("text", "") or "")
            elif item_type in {"citation", "url_citation"}:
                url = str(item.get("url", "") or item.get("href", "") or "")
                title = str(item.get("title", "") or url or "Source")
                if url:
                    sources.append({"title": title, "href": url})
            elif item_type == "web_search_call":
                action = item.get("action") or {}
                for source in action.get("sources", []) or []:
                    if not isinstance(source, dict):
                        continue
                    href = str(source.get("url", "") or "")
                    title = str(source.get("title", "") or href or "Source")
                    if href:
                        sources.append({"title": title, "href": href})

    response_metadata = getattr(ai_message, "response_metadata", None) or {}
    metadata_citations = response_metadata.get("citations") or []
    for citation in metadata_citations:
        if not isinstance(citation, dict):
            continue
        href = str(
            citation.get("url", "")
            or citation.get("source", "")
            or citation.get("href", "")
            or ""
        )
        title = str(citation.get("title", "") or href or "Source")
        if href:
            sources.append({"title": title, "href": href})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (source["title"], source["href"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)

    return output_text.strip(), deduped


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(run_knowledge_worker(stop_event))
    app.state.stop_event = stop_event
    app.state.worker_task = worker_task
    try:
        yield
    finally:
        stop_event.set()
        try:
            await worker_task
        except Exception:
            pass


def build_app() -> FastAPI:
    app = FastAPI(title="chat_llm backend", version="0.1.0", lifespan=app_lifespan)

    upload_root = (Path(__file__).resolve().parent / "knowledge")
    delete_tasks: dict[int, asyncio.Task] = {}

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

    llm = KnowledgeAssistantAgent()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/models")
    async def list_models():
        return {
            "default": DEFAULT_CHAT_MODEL,
            "models": [
                {"id": model_id, **metadata}
                for model_id, metadata in SUPPORTED_CHAT_MODELS.items()
            ],
        }

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
        model_id = str(payload.get("model") or DEFAULT_CHAT_MODEL).strip() or DEFAULT_CHAT_MODEL
        top_k = int(payload.get("top_k") or 10)
        use_web_search = bool(payload.get("use_web_search"))

        if not is_supported_chat_model(model_id):
            raise HTTPException(status_code=400, detail="unsupported model")

        logger.info(
            "[rid=%s] /chat: session_id=%s model_id=%s query_len=%s top_k=%s categories=%s use_web_search=%s",
            request_id,
            session_id,
            model_id,
            len(query),
            top_k,
            categories_list,
            use_web_search,
        )

        if use_web_search:
            async def gen_web_search():
                import json

                tool_intent_patterns = (
                    "what tools do you have",
                    "what are the tools you have access",
                    "available tools",
                    "which tools do you have",
                    "what tools can you use",
                )
                lowered_query = query.lower()

                if any(pattern in lowered_query for pattern in tool_intent_patterns):
                    tool_summary = (
                        "Available Tools\n\n"
                        "When Search is enabled, the active tool is:\n\n"
                        "1. web_search_preview\n"
                        "   Description: Retrieves current information from the web using OCI OpenAI web search.\n"
                        "   Use cases: latest news, recent events, live information, and web citations.\n\n"
                        "When Search is enabled for this message, semantic_search and nl2sql_tool are not used for the answer path."
                    )
                    yield json.dumps({
                        "updates": "Model calling tool: web_search with args {\"query\": \"tool capability summary\"}"
                    }) + "\n"
                    yield json.dumps({
                        "updates": "Tool web_search responded with:\nSearch mode is enabled; web_search_preview is the active tool for this request."
                    }) + "\n"
                    yield json.dumps({
                        "type": "final",
                        "is_task_complete": True,
                        "content": tool_summary,
                        "token_count": "0",
                    }) + "\n"
                    return

                yield json.dumps({
                    "updates": "Model calling tool: web_search with args {\"query\": %s}" % json.dumps(query)
                }) + "\n"

                try:
                    client = _build_oci_web_search_client()
                    search_model = client.bind_tools([{"type": "web_search_preview"}])
                    response = await asyncio.to_thread(
                        search_model.invoke,
                        [HumanMessage(content=query)],
                    )
                    final_content, sources = _extract_web_search_payload(response)
                    yield json.dumps({
                        "updates": "Tool web_search responded with:\n" + (final_content or "No web search result returned."),
                    }) + "\n"
                    yield json.dumps({
                        "type": "final",
                        "is_task_complete": True,
                        "content": final_content or "No web search result returned.",
                        "sources": sources,
                        "token_count": "0",
                    }) + "\n"
                except Exception as exc:
                    logger.exception("[rid=%s] web search request failed: %s", request_id, exc)
                    yield json.dumps({"updates": f"Tool web_search responded with:\nError: {str(exc)}"}) + "\n"
                    yield json.dumps({
                        "type": "final",
                        "is_task_complete": True,
                        "content": (
                            "Web search is enabled, but this OCI OpenAI web-search path is not configured for your current environment. "
                            "Your app currently has SERVICE_ENDPOINT/AUTH_PROFILE OCI auth for ChatOCIGenAI, but no OCI/OpenAI API key is configured for the OpenAI-compatible web-search endpoint. "
                            f"Underlying error: {str(exc)}"
                        ),
                        "token_count": "0",
                    }) + "\n"

            return StreamingResponse(gen_web_search(), media_type="application/x-ndjson")

        use_semantic_search = _should_use_semantic_search(query, categories_list)

        rag_context: str = ""
        nl2sql_result: str = ""

        q_lower = str(query or "").lower()
        restaurant_keywords = (
            "restaurant",
            "restaurants",
            "menu",
            "menus",
            "menu item",
            "menu items",
            "dish",
            "dishes",
            "cuisine",
            "cuisines",
        )
        restaurant_entity_keywords = (
            "sunrise bistro",
            "spice route kitchen",
            "san francisco",
            "los angeles",
            "new york",
        )
        restaurant_attribute_keywords = (
            "price",
            "available",
            "location",
            "address",
            "city",
        )
        use_nl2sql = any(k in q_lower for k in restaurant_keywords) or (
            any(k in q_lower for k in restaurant_attribute_keywords)
            and any(k in q_lower for k in restaurant_entity_keywords)
        )
        use_agentic_chat = not use_nl2sql and not categories_list and not use_semantic_search

        if use_agentic_chat:
            logger.info(
                "[rid=%s] /chat: routing to agentic chat path (model decides tool usage)",
                request_id,
            )

            async def gen_agentic():
                agent = KnowledgeAssistantAgent(model_id=model_id)
                async for chunk in agent.oci_stream(query, session_id=session_id):
                    import json

                    yield json.dumps(chunk) + "\n"

            return StreamingResponse(
                gen_agentic(),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        async def gen():
            import json

            current_nl2sql_result = ""
            current_rag_context = ""

            if use_nl2sql:
                yield json.dumps(
                    {
                        "updates": "Model calling tool: nl2sql_tool with args "
                        + json.dumps({"question": query})
                    }
                ) + "\n"

                try:
                    from chat_app.nl2sql_tool import nl2sql_tool

                    current_nl2sql_result = await nl2sql_tool.ainvoke({"question": query})
                except Exception as e:
                    logger.warning("[rid=%s] nl2sql_tool failed: %s", request_id, str(e))
                    current_nl2sql_result = ""

                if current_nl2sql_result:
                    yield json.dumps(
                        {"updates": "Tool nl2sql_tool responded with:\n" + str(current_nl2sql_result)}
                    ) + "\n"

            if use_semantic_search:
                yield json.dumps(
                    {
                        "updates": "Model calling tool: semantic_search with args "
                        + json.dumps({"query": query, "top_k": top_k, "categories": categories_list})
                    }
                ) + "\n"

                try:
                    from chat_app.rag_tool import semantic_search_raw

                    current_rag_context = await semantic_search_raw(
                        query=query,
                        top_k=top_k,
                        categories=categories_list,
                        request_id=request_id,
                    )
                except Exception as e:
                    logger.warning("[rid=%s] semantic_search failed: %s", request_id, str(e))
                    current_rag_context = ""
            else:
                logger.info(
                    "[rid=%s] /chat: skipping semantic_search for conversational query",
                    request_id,
                )

            logger.info(
                "[rid=%s] /chat: nl2sql_selected=%s semantic_search_selected=%s nl2sql_present=%s rag_context_present=%s",
                request_id,
                use_nl2sql,
                use_semantic_search,
                bool(current_nl2sql_result),
                bool(current_rag_context and "No relevant documents found" not in current_rag_context),
            )

            if current_rag_context:
                yield json.dumps(
                    {"updates": "Tool semantic_search responded with:\n" + str(current_rag_context)}
                ) + "\n"

            # Stream chunks as NDJSON so the frontend can update incrementally.
            augmented = query
            selected_cats = categories_list
            if current_nl2sql_result:
                augmented = (
                    "You are answering a user question using database query results and retrieved knowledge snippets.\n"
                    "Use the database results below as the source of truth for structured facts such as restaurant names, addresses, coordinates, menu items, prices, and availability.\n"
                    "Use the retrieved knowledge snippets to enrich the answer with cuisine profile, what customers like, menu highlights, and review-style qualitative details when available.\n"
                    "Respond in clear markdown.\n"
                    "Start with a short direct answer to the user's question.\n"
                    "When the question asks for menu items, restaurants, comparisons, or 'both restaurants', include a markdown table.\n"
                    "For menu-style questions, prefer a table with columns like: Restaurant | Item | Category | Price | Available.\n"
                    "For menu-style questions, append a Mermaid flowchart code block at the end of the response.\n"
                    "The Mermaid block must be fenced as ```mermaid and should use a simple flowchart that starts from the restaurant name and branches to each menu item.\n"
                    "For each menu item, include whether it is Vegan, Veg, or Non-Veg when that can be reasonably inferred from the item name or description; otherwise label it Unknown.\n"
                    "Keep Mermaid node labels short and frontend-friendly, for example: Restaurant --> Item --> Vegan, Veg, or Non-Veg.\n"
                    "If the question is about restaurants in a city or area, first show a markdown table for the restaurant details. Prefer columns like: Restaurant | Address | City | State | Image.\n"
                    "After the table, add a separate section titled 'Customer Reviews and Highlights' and summarize each restaurant using the retrieved knowledge snippets.\n"
                    "In that section, include cuisine profile, what customers like, and notable menu items when available.\n"
                    "If the tool result already contains a markdown table, preserve or reuse that table and add a short summary below it.\n"
                    "Do not say that no reviews, menus, or additional details are available if the retrieved knowledge snippets contain them.\n"
                    "Then provide a concise explanation of what the results mean.\n"
                    "If useful, summarize the best matches as bullet points.\n"
                    "If the results are empty, say no matching records were found.\n"
                    "Do not dump raw tool output without explanation.\n\n"
                    f"Database results:\n{current_nl2sql_result}\n\n"
                    f"Retrieved knowledge snippets (each snippet includes a Source):\n{current_rag_context if current_rag_context else 'No additional retrieved knowledge snippets were found.'}\n\n"
                    f"User question:\n{query}\n\n"
                    "Answer:\n"
                )
            elif current_rag_context:
                augmented = (
                    "You are answering a user question using retrieved knowledge snippets.\n"
                    "Follow these rules:\n"
                    "- Treat the retrieved context as the primary source of truth.\n"
                    "- If Selected knowledge categories is non-empty, only rely on information that fits those categories.\n"
                    "- Do not say 'no relevant context found' because context IS provided below.\n"
                    "- If the context does not contain the answer, say what is missing and ask a brief clarifying question.\n\n"
                    f"Selected knowledge categories: {selected_cats if selected_cats else '[]'}\n\n"
                    f"Retrieved context (each snippet includes a Source):\n{current_rag_context}\n\n"
                    f"User question:\n{query}\n\n"
                    "Answer:\n"
                )
            else:
                augmented = (
                    "You are a helpful conversational assistant.\n"
                    "Respond naturally and directly to the user's message.\n"
                    "Do not mention retrieval, missing documents, knowledge base context, or tool usage unless the user explicitly asks about them.\n"
                    "If the user's message is casual small talk, reply conversationally and briefly.\n"
                    "If the user asks for factual help that does not require the knowledge base, answer normally using general knowledge.\n\n"
                    f"User message:\n{query}\n\n"
                    "Assistant reply:\n"
                )

            assembled_response = ""
            async for text_chunk in stream_augmented_response(
                augmented,
                model_id=model_id,
            ):
                assembled_response += str(text_chunk)
                yield json.dumps(
                    {
                        "type": "delta",
                        "is_task_complete": False,
                        "delta": str(text_chunk),
                    }
                ) + "\n"

            suggestions_json = None
            try:
                suggestions = await llm._suggestion_out.ainvoke(
                    llm._out_query
                    + f"\n\nContext for question generation:\n{assembled_response}"
                )
                if suggestions:
                    suggestions_json = suggestions.model_dump_json()
            except Exception:
                logger.exception("[rid=%s] suggestion generation failed", request_id)

            yield json.dumps(
                {
                    "type": "final",
                    "is_task_complete": True,
                    "content": assembled_response,
                    "token_count": "0",
                    "suggestions": suggestions_json,
                }
            ) + "\n"

        return StreamingResponse(
            gen(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

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

    async def _run_knowledge_delete_job(job_id: int, category: str) -> None:
        """Delete a knowledge category from filesystem + DB in the background."""
        cat = _safe_category(category)
        cat_dir = (upload_root / cat).resolve()
        upload_root_resolved = upload_root.resolve()

        db = RAGDBConnection()
        deleted_embeddings = 0
        deleted_files = 0
        deleted_job_links = 0
        embedding_cleanup_ok = True

        logger.info("Starting async knowledge category delete for '%s' (job=%s)", cat, job_id)

        try:
            with db.get_connection() as conn:
                update_knowledge_job(
                    conn,
                    db.table_prefix,
                    job_id,
                    status="running",
                    progress_pct=5,
                    message=f"delete:{cat}:starting",
                )
        except Exception:
            logger.exception("Failed to mark delete job %s as running", job_id)

        try:
            with db.get_connection() as conn:
                ensure_knowledge_tables(conn, db.table_prefix)
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, storage_path
                        FROM {db.table_prefix}_knowledge_file
                        WHERE category = :cat
                        """,
                        {"cat": cat},
                    )
                    category_files = cur.fetchall() or []

                    logger.info(
                        "Category '%s' has %s knowledge file rows to delete",
                        cat,
                        len(category_files),
                    )

                    update_knowledge_job(
                        conn,
                        db.table_prefix,
                        job_id,
                        progress_pct=20,
                        message=f"delete:{cat}:loaded {len(category_files)} files",
                    )

                    sources_to_delete: set[str] = set()
                    filename_patterns: set[str] = set()
                    file_ids: list[int] = []
                    for row in category_files:
                        if not row:
                            continue
                        file_id = int(row[0])
                        storage_path = str(row[1] or "").replace("\\", "/")
                        if not storage_path:
                            continue

                        file_ids.append(file_id)
                        abs_path = str((upload_root_resolved / storage_path).resolve()).replace("\\", "/")
                        filename = Path(storage_path).name
                        sources_to_delete.add(storage_path)
                        sources_to_delete.add(abs_path)
                        filename_patterns.add(f"%/{filename}")
                        filename_patterns.add(f"%/{filename}_start_%")

                    if sources_to_delete:
                        bind_names = []
                        bind_values: dict[str, str] = {}
                        for idx, source in enumerate(sorted(sources_to_delete)):
                            bind_name = f"src_{idx}"
                            bind_names.append(f":{bind_name}")
                            bind_values[bind_name] = source

                        try:
                            cur.execute(
                                f"DELETE FROM {db.table_prefix}_embedding WHERE source IN ({', '.join(bind_names)})",
                                bind_values,
                            )
                            deleted_embeddings = int(cur.rowcount or 0)

                            # Legacy fallback: older rows stored absolute PDF paths and chunk suffixes.
                            # Restrict fallback to the category's filenames so we avoid a broad full-table scan.
                            if filename_patterns:
                                pattern_clauses = []
                                pattern_binds: dict[str, str] = {}
                                for idx, pattern in enumerate(sorted(filename_patterns)):
                                    bind_name = f"pattern_{idx}"
                                    pattern_clauses.append(f"REPLACE(source, '\\', '/') LIKE :{bind_name}")
                                    pattern_binds[bind_name] = pattern

                                cur.execute(
                                    f"DELETE FROM {db.table_prefix}_embedding WHERE {' OR '.join(pattern_clauses)}",
                                    pattern_binds,
                                )
                                deleted_embeddings += int(cur.rowcount or 0)
                        except Exception as embedding_err:
                            embedding_cleanup_ok = False
                            logger.warning(
                                "Embedding cleanup for category '%s' did not complete inline: %s",
                                cat,
                                str(embedding_err),
                            )
                            conn.rollback()
                            ensure_knowledge_tables(conn, db.table_prefix)
                            with conn.cursor() as retry_cur:
                                if file_ids:
                                    file_id_binds = []
                                    file_id_values: dict[str, int] = {}
                                    for idx, file_id in enumerate(file_ids):
                                        bind_name = f"file_id_retry_{idx}"
                                        file_id_binds.append(f":{bind_name}")
                                        file_id_values[bind_name] = file_id
                                    retry_cur.execute(
                                        f"DELETE FROM {db.table_prefix}_knowledge_job_file WHERE file_id IN ({', '.join(file_id_binds)})",
                                        file_id_values,
                                    )
                                    deleted_job_links = int(retry_cur.rowcount or 0)
                                else:
                                    deleted_job_links = 0

                                retry_cur.execute(
                                    f"DELETE FROM {db.table_prefix}_knowledge_file WHERE category = :cat",
                                    {"cat": cat},
                                )
                                deleted_files = int(retry_cur.rowcount or 0)

                            conn.commit()
                            logger.info(
                                "Deleted metadata for category '%s' even though embedding cleanup was deferred",
                                cat,
                            )
                            deleted_embeddings = 0
                    else:
                        deleted_embeddings = 0

                    logger.info(
                        "Deleted %s embedding rows for category '%s'",
                        deleted_embeddings,
                        cat,
                    )

                    update_knowledge_job(
                        conn,
                        db.table_prefix,
                        job_id,
                        progress_pct=65,
                        message=f"delete:{cat}:deleted embeddings={deleted_embeddings}",
                    )

                    # Delete job-file links for this category's files.
                    if file_ids:
                        file_id_binds = []
                        file_id_values: dict[str, int] = {}
                        for idx, file_id in enumerate(file_ids):
                            bind_name = f"file_id_{idx}"
                            file_id_binds.append(f":{bind_name}")
                            file_id_values[bind_name] = file_id

                        cur.execute(
                            f"DELETE FROM {db.table_prefix}_knowledge_job_file WHERE file_id IN ({', '.join(file_id_binds)})",
                            file_id_values,
                        )
                        deleted_job_links = int(cur.rowcount or 0)
                    else:
                        deleted_job_links = 0

                    logger.info(
                        "Deleted %s job-file link rows for category '%s'",
                        deleted_job_links,
                        cat,
                    )

                    # Delete file records for this category.
                    cur.execute(
                        f"DELETE FROM {db.table_prefix}_knowledge_file WHERE category = :cat",
                        {"cat": cat},
                    )
                    deleted_files = int(cur.rowcount or 0)

                    logger.info(
                        "Deleted %s knowledge_file rows for category '%s'",
                        deleted_files,
                        cat,
                    )

                    update_knowledge_job(
                        conn,
                        db.table_prefix,
                        job_id,
                        progress_pct=85,
                        message=f"delete:{cat}:deleted files={deleted_files}",
                    )

                conn.commit()
        except Exception as e:
            logger.exception("Failed deleting category from DB: %s", str(e))
            try:
                with db.get_connection() as conn:
                    finish_knowledge_job(
                        conn,
                        db.table_prefix,
                        job_id,
                        ok=False,
                        message=f"delete:{cat}:failed:{str(e)[:900]}",
                    )
            finally:
                delete_tasks.pop(job_id, None)
            return

        deleted_fs = False
        try:
            if cat_dir.exists() and cat_dir.is_dir():
                shutil.rmtree(cat_dir)
                deleted_fs = True
        except Exception as e:
            logger.warning("Failed deleting category folder '%s': %s", cat, str(e))

        logger.info("Completed knowledge category delete for '%s'", cat)

        try:
            with db.get_connection() as conn:
                finish_knowledge_job(
                    conn,
                    db.table_prefix,
                    job_id,
                    ok=True,
                    message=(
                        f"delete:{cat}:completed:embedding_cleanup_ok={embedding_cleanup_ok};"
                        f"embeddings={deleted_embeddings};files={deleted_files};job_links={deleted_job_links};fs={deleted_fs}"
                    )[:1000],
                )
        finally:
            delete_tasks.pop(job_id, None)

    @app.post("/knowledge/category/{category}/delete")
    async def knowledge_delete_category_start(category: str):
        cat = _safe_category(category)
        db = RAGDBConnection()
        with db.get_connection() as conn:
            ensure_knowledge_tables(conn, db.table_prefix)
            job_id = create_knowledge_delete_job(conn, db.table_prefix, cat)

        delete_tasks[job_id] = asyncio.create_task(_run_knowledge_delete_job(job_id, cat))

        return {
            "ok": True,
            "job_id": job_id,
            "category": cat,
            "status": "queued",
        }

    @app.get("/knowledge/category-delete-jobs/{job_id}")
    async def knowledge_delete_category_status(job_id: int):
        db = RAGDBConnection()
        with db.get_connection() as conn:
            ensure_knowledge_tables(conn, db.table_prefix)
            job = get_knowledge_delete_job(conn, db.table_prefix, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="delete job not found")

        return {
            "ok": True,
            "job": job,
        }

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
