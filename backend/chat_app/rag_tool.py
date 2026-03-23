import array
import logging
import os
from langchain.tools import tool

from core.gen_ai_provider import GenAIEmbedProvider
from database.connections import RAGDBConnection

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
DEFAULT_MAX_DISTANCE = float(os.getenv("SEMANTIC_SEARCH_MAX_DISTANCE", "0.58"))

def build_context_snippet(results: list[dict]) -> str:
    """Format retrieved chunks for prompt context."""
    if not results:
        return "No relevant documents found."
    context_parts = []
    for i, r in enumerate(results, 1):
        text_val = r.get("text")
        # Oracle CLOB may arrive as a LOB object; convert safely.
        if hasattr(text_val, "read"):
            try:
                text_val = text_val.read()
            except Exception:
                text_val = str(text_val)
        snippet = str(text_val or "").replace("\n", " ")
        context_parts.append(f"[{i}] (Source: {r['source']}) {snippet}")
    return "\n\n".join(context_parts)


async def semantic_search_raw(
    query: str,
    top_k: int = 10,
    categories: list[str] | None = None,
    request_id: str | None = None,
) -> str:
    """Plain async function for semantic retrieval (callable from API code).

    The @tool-wrapped variant below delegates to this.
    """
    embed_provider = GenAIEmbedProvider()
    db_conn = RAGDBConnection()

    try:
        rid = request_id or "-"
        cat_list = [str(c).strip() for c in (categories or []) if str(c).strip()]
        logger.info(
            "[rid=%s] semantic_search_raw: query_len=%s top_k=%s categories=%s prefix=%s",
            rid,
            len(query or ""),
            int(top_k),
            cat_list,
            db_conn.table_prefix,
        )

        query_response = embed_provider.embed_client.embed_query(query)
        query_vec = array.array("f", query_response)
        logger.info("[rid=%s] semantic_search_raw: embedded query vector_len=%s", rid, len(query_vec))

        with db_conn.get_connection() as connection:
            cursor = connection.cursor()

            if cat_list:
                # Normalize embedding source paths to match knowledge_file.storage_path.
                # `base_root` is the on-disk knowledge folder as a forward-slash prefix.
                base_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge"))
                base_root = base_root.replace("\\", "/").rstrip("/") + "/"

                bind = {"query_vec": query_vec, "base_root": base_root}
                cat_binds = []
                for i, cat in enumerate(cat_list):
                    k = f"cat{i}"
                    bind[k] = cat
                    cat_binds.append(f":{k}")
                placeholders = ",".join(cat_binds)
                logger.info(
                    "[rid=%s] semantic_search_raw: executing category-filtered SQL (cats=%s)",
                    rid,
                    cat_list,
                )
                cursor.execute(
                    f"""
                    SELECT e.text,
                           vector_distance(e.embedding_vector, :query_vec, COSINE) AS distance,
                           e.source
                    FROM {db_conn.table_prefix}_embedding e
                    WHERE EXISTS (
                        SELECT 1
                        FROM {db_conn.table_prefix}_knowledge_file f
                                                WHERE (
                                                    -- embeddings currently store absolute Windows paths, while knowledge_file.storage_path
                                                    -- stores a relative path like "deployment/file.pdf".
                                                    -- Also, some sources include a chunk suffix like "...pdf_start_0".
                                                    f.storage_path = REPLACE(REPLACE(e.source, '\\', '/'), :base_root, '')
                                                    OR (
                                                        REPLACE(REPLACE(e.source, '\\', '/'), :base_root, '') LIKE f.storage_path || '%'
                                                    )
                                                    OR (
                                                        -- Fallback: match by just the filename (handles absolute paths).
                                                        SUBSTR(REPLACE(REPLACE(e.source, '\\', '/'), :base_root, ''),
                                                                     INSTR(REPLACE(REPLACE(e.source, '\\', '/'), :base_root, ''), '/', -1) + 1
                                                        ) = SUBSTR(f.storage_path, INSTR(f.storage_path, '/', -1) + 1)
                                                    )
                                                )
                          AND f.category IN ({placeholders})
                    )
                    ORDER BY distance
                    FETCH FIRST {top_k} ROWS ONLY
                    """,
                                        bind,
                )
            else:
                logger.info("[rid=%s] semantic_search_raw: executing unfiltered SQL", rid)
                cursor.execute(
                    f"""
                    SELECT text, vector_distance(embedding_vector, :1, COSINE) AS distance, source
                    FROM {db_conn.table_prefix}_embedding
                    ORDER BY distance
                    FETCH FIRST {top_k} ROWS ONLY
                    """,
                    [query_vec],
                )

            rows = cursor.fetchall()
            results = [{"text": r[0], "distance": r[1], "source": r[2]} for r in rows]
            cursor.close()

        logger.info("[rid=%s] semantic_search_raw: hits=%s", rid, len(results))
        if results:
            preview = [
                {
                    "source": str(r.get("source")),
                    "distance": None if r.get("distance") is None else float(r.get("distance")),
                }
                for r in results[: min(5, len(results))]
            ]
            logger.info("[rid=%s] semantic_search_raw: top_hits=%s", rid, preview)

            filtered_results = [
                row
                for row in results
                if row.get("distance") is not None and float(row["distance"]) <= DEFAULT_MAX_DISTANCE
            ]
            logger.info(
                "[rid=%s] semantic_search_raw: filtered_hits=%s max_distance=%s",
                rid,
                len(filtered_results),
                DEFAULT_MAX_DISTANCE,
            )
            if not filtered_results:
                logger.info(
                    "[rid=%s] semantic_search_raw: no hits passed similarity threshold",
                    rid,
                )
                return "No relevant documents found."

            results = filtered_results

        return build_context_snippet(results)
    except Exception:
        rid = request_id or "-"
        logger.exception("[rid=%s] semantic_search_raw failed", rid)
        return "Error performing semantic search."

@tool()
async def semantic_search(query: str, top_k: int = 10, categories: list[str] | None = None) -> str:
    """Retrieve knowledge-base passages only when the user is explicitly asking for document-grounded information.

    Do not use this for greetings, small talk, vague follow-ups, or general conversation.
    """
    
    return await semantic_search_raw(query=query, top_k=top_k, categories=categories)