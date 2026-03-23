# Chat LLM Monorepo

This project is a full-stack AI chat application with:

- a **Next.js frontend** for chat and knowledge upload
- a **FastAPI backend** for chat streaming, RAG search, and PDF ingestion
- an **Oracle-backed knowledge pipeline** for embeddings and job tracking

The app supports:

- chat with streamed AI responses
- retrieval-augmented generation (RAG) over uploaded PDF knowledge
- category-based knowledge filtering
- NL2SQL-style answers for restaurant/menu-related queries
- knowledge upload and batch job tracking
- a local profile page for goals, interests, and saved source links
- profile-based web updates using Crawl4AI over saved links

## Project structure

```text
chat_llm/
├─ frontend/                 # Next.js app
├─ backend/                  # FastAPI + LLM + RAG logic
├─ database/                 # DB wallet + SQL migrations
├─ openspec/                 # spec/change artifacts
├─ package.json              # root dev runner
└─ README.md
```

## Tech stack

### Frontend

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- shadcn/ui and custom AI UI components

### Backend

- FastAPI
- Python 3.13+
- LangChain / LangGraph
- OCI GenAI via `langchain-oci`
- Oracle DB via `oracledb`
- Crawl4AI + Playwright for profile-based web crawling

## How the project works

### Chat flow

1. The user asks a question in the frontend chat UI.
2. The frontend sends the request to `POST /chat` on the backend.
3. The backend decides whether to:
   - run **semantic search** over uploaded knowledge, or
   - run **NL2SQL** for restaurant/menu related questions.
4. The backend streams the answer back as NDJSON.
5. The frontend renders:
   - assistant response text
   - tool activity/status updates
   - follow-up suggestions

### Profile update flow

1. The user saves goals, interests, and web source links from the frontend profile page.
2. The frontend stores this profile in local storage and includes it in chat requests.
3. When the user asks for things like `update me`, `latest news`, or `what's new`, the backend checks the saved profile links.
4. Crawl4AI fetches content from the saved pages.
5. The model produces a personalized update explaining why the latest information matters for the user's goals and interests.

### Knowledge flow

1. The user uploads one or more PDF files from the **Knowledge** page.
2. The backend stores files under `backend/knowledge/<category>/`.
3. A knowledge job is created in Oracle.
4. A background worker processes the PDFs, chunks text, creates embeddings, and stores them in the embedding table.
5. Uploaded categories become selectable in the chat UI.

## Prerequisites

Before setup, make sure you have:

- **Node.js** installed
- **pnpm** installed
- **Python 3.13+** installed
- **uv** installed for Python dependency management
- access to **Oracle Cloud / OCI GenAI**
- an **Oracle DB connection / wallet** if you want RAG + job tracking to work fully

## Setup

## 1. Clone and open the project

Open the project folder in VS Code or terminal:

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm"
```

## 2. Install root dependencies

The root project uses `concurrently` to run frontend and backend together.

```powershell
pnpm install
```

## 3. Setup the frontend

Install frontend dependencies:

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\frontend"
pnpm install
```

Optional environment variable for custom backend URL:

```env
NEXT_PUBLIC_CHAT_API_BASE=http://localhost:8000
```

If not set, the frontend already defaults to `http://localhost:8000`.

## 4. Setup the backend

Install backend dependencies with `uv`:

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\backend"
uv sync
```

This creates a local virtual environment in `backend/.venv`.

If you want profile-based web updates using Crawl4AI, also install Playwright browser binaries:

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\backend"
uv run python -m playwright install
```

Without this step, normal chat still works, but profile-based web crawling cannot start.

## 5. Configure backend environment

Create a `.env` file inside `backend/`.

At minimum, the backend expects OCI configuration values used by `ChatOCIGenAI`:

```env
SERVICE_ENDPOINT=your_oci_genai_endpoint
COMPARTMENT_ID=your_compartment_ocid
AUTH_PROFILE=DEFAULT
```

You will also likely need Oracle DB connection settings for:

- knowledge jobs
- embedding table writes
- category listing from DB
- semantic search / NL2SQL features

The exact DB variables are used by the backend database connection layer in `backend/database/connections.py`.

In addition, the repository already contains an Oracle wallet under:

```text
database/Wallet_InnLabDatalakeDB/
```

If your environment requires it, make sure your `.env` points to the correct wallet/config values.

## 6. Apply database migrations

If you are setting up the database for the first time, run the migration script:

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\backend"
.\.venv\Scripts\python.exe .\scripts\apply_migrations.py
```

Migration SQL files live in:

```text
database/migrations/
```

## Running the project

### Run frontend and backend together

From the repository root:

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm"
pnpm dev
```

This uses the root script to start:

- backend on `http://localhost:8000`
- frontend on `http://localhost:3000`

### Run backend only

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\backend"
.\.venv\Scripts\python.exe .\__main__.py --host 0.0.0.0 --port 8000
```

### Run frontend only

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\frontend"
pnpm dev
```

## URLs

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/health`
- Knowledge page: `http://localhost:3000/knowledge`

## Main backend APIs

### Chat

- `POST /chat`  
  Send chat requests and receive streamed NDJSON responses.

Example request body:

```json
{
  "query": "Summarize outage preparedness guidance",
  "session_id": "local",
  "profile": {
    "goals": ["Track AI product launches"],
    "interests": ["AI agents", "LangGraph"],
    "links": [
      {"label": "TechCrunch", "url": "https://techcrunch.com/"}
    ]
  },
  "categories": ["general"],
  "top_k": 10
}
```

### Knowledge

- `POST /knowledge/upload` - upload one or more PDF files
- `GET /knowledge/jobs/{job_id}` - check knowledge batch job status
- `GET /knowledge/list` - list uploaded knowledge files/categories
- `GET /knowledge/categories` - list available categories
- `GET /health` - backend health check

## Available features

- **Chat UI** with streaming responses
- **Tool status display** in the frontend
- **Knowledge category selection** before asking questions
- **PDF upload UI** for building knowledge collections
- **Batch ingestion jobs** for embeddings
- **Restaurant/menu DB query mode** via NL2SQL detection
- **Profile page** for saved goals, interests, and source links
- **Crawl4AI-powered updates** from user-saved web pages

## Development notes

- The backend runs a background knowledge worker on FastAPI startup.
- Uploaded files are stored locally in `backend/knowledge/`.
- Sample RAG documents are included in `backend/core/rag_docs/`.
- The frontend is already wired to the backend using `NEXT_PUBLIC_CHAT_API_BASE` or `http://localhost:8000` by default.
- The profile page stores user context in browser local storage only.
- Crawl4AI-based updates require Playwright browser installation in the backend environment.

## Common setup issues

### Frontend cannot reach backend

Make sure:

- backend is running on port `8000`
- frontend is using the correct `NEXT_PUBLIC_CHAT_API_BASE`
- no firewall/proxy is blocking localhost ports

### Knowledge upload works but jobs fail

Make sure Oracle DB connectivity, wallet configuration, and embedding tables are correctly set up.

### Profile-based updates fail with Playwright or Crawl4AI errors

Make sure:

- backend dependencies were installed with `uv sync`
- Playwright browsers were installed with `uv run python -m playwright install`
- saved profile links are reachable from the backend machine

If Playwright browsers are missing, the profile update flow will return a setup-related message instead of crawling pages.

This usually means:

- Oracle DB is not configured correctly
- wallet path/settings are wrong
- required tables were not migrated
- OCI embedding configuration is incomplete

### Chat works but RAG does not return useful results

Check:

- PDFs were uploaded successfully
- the background worker processed the job
- embeddings were written to the DB
- selected categories match the uploaded category names

## Helpful commands

### Install everything

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm"
pnpm install
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\frontend"
pnpm install
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\backend"
uv sync
```

### Lint frontend

```powershell
Set-Location "c:\Users\AJay\Desktop\order_dossier\chat_llm\frontend"
pnpm lint
```

### Check backend health

```powershell
Invoke-WebRequest "http://localhost:8000/health"
```

## About this project

This repository appears to be a demo/working prototype for an AI-powered knowledge assistant focused on:

- general knowledge retrieval from PDFs
- outage/energy-related assistance
- Oracle Cloud GenAI integration
- Oracle database-backed retrieval and ingestion workflows

It combines a modern AI chat frontend with a backend that supports streaming responses, RAG, and structured data querying.