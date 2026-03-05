# chat_llm backend

Standalone backend for the chat LLM service.

## Quickstart (uv)

```powershell
cd chat_llm/backend
uv sync
```

## Run server (single entrypoint)

This backend is started via `__main__.py`:

```powershell
cd chat_llm/backend
.\.venv\Scripts\python.exe .\__main__.py --host 0.0.0.0 --port 8000
```

Health check:

- http://localhost:8000/health

## Notes

- Configuration is via `.env` (OCI GenAI + DB wallet settings).
- RAG PDFs are stored in `core/rag_docs/`.
