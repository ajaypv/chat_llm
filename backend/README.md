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

## Knowledge (PDF upload + embeddings)

Upload PDFs to build the vector store:

- `POST /knowledge/upload` (multipart form-data)
	- `category`: folder name (A-Z, 0-9, `_`, `-`)
	- `files`: one or more PDF files

Files are stored on disk under:

- `backend/knowledge/<category>/*.pdf`

When a PDF is uploaded, the backend enqueues an embedding job in Oracle and a background worker (running inside the FastAPI process) will:

- load/chunk the PDF
- generate embeddings via OCI GenAI
- insert vectors into `{DB_TABLE_PREFIX}_embedding`

Job status:

- `GET /knowledge/jobs/{job_id}`

## Notes

- Configuration is via `.env` (OCI GenAI + DB wallet settings).
- RAG PDFs are stored in `core/rag_docs/`.
