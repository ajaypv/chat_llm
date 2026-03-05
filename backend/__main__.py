import logging

import click
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from chat_app.main_llm import OCIOutageEnergyLLM

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_app() -> FastAPI:
    app = FastAPI(title="chat_llm backend", version="0.1.0")

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

        session_id = payload.get("session_id") or "local"

        async def gen():
            import json
            # Stream chunks as NDJSON so the frontend can update incrementally.
            async for chunk in llm.oci_stream(query, session_id=session_id):
                yield json.dumps(chunk) + "\n"

        return StreamingResponse(gen(), media_type="application/x-ndjson")

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
