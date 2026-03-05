import array
from langchain.tools import tool

from core.gen_ai_provider import GenAIEmbedProvider
from database.connections import RAGDBConnection

from dotenv import load_dotenv
load_dotenv()

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


async def semantic_search_raw(query: str, top_k: int = 3, categories: list[str] | None = None) -> str:
    """Plain async function for semantic retrieval (callable from API code).

    The @tool-wrapped variant below delegates to this.
    """
    embed_provider = GenAIEmbedProvider()
    db_conn = RAGDBConnection()

    try:
        query_response = embed_provider.embed_client.embed_query(query)
        query_vec = array.array("f", query_response)

        with db_conn.get_connection() as connection:
            cursor = connection.cursor()

            cat_list = [str(c).strip() for c in (categories or []) if str(c).strip()]
            if cat_list:
                binds: list[object] = [query_vec]
                placeholders = ",".join([f":{i+2}" for i in range(len(cat_list))])
                binds.extend(cat_list)
                cursor.execute(
                    f"""
                    SELECT e.text,
                           vector_distance(e.embedding_vector, :1, COSINE) AS distance,
                           e.source
                    FROM {db_conn.table_prefix}_embedding e
                    WHERE EXISTS (
                        SELECT 1
                        FROM {db_conn.table_prefix}_knowledge_file f
                        WHERE f.storage_path = e.source
                          AND f.category IN ({placeholders})
                    )
                    ORDER BY distance
                    FETCH FIRST {top_k} ROWS ONLY
                    """,
                    binds,
                )
            else:
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

        return build_context_snippet(results)
    except Exception as e:
        return f"Error performing semantic search: {str(e)}"

@tool()
async def semantic_search(query: str, top_k: int = 3, categories: list[str] | None = None) -> str:
    """Perform semantic search with cosine similarity to find relevant documents:
    [epa_actions_for_outages (US), fema_outage_flyer (US), general_disaster_manual (MEX)]
    """
    
    return await semantic_search_raw(query=query, top_k=top_k, categories=categories)