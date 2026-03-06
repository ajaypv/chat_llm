import re
import textwrap
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage
from langchain.tools import tool

from core.gen_ai_provider import GenAIProvider
from database.connections import RAGDBConnection

def _build_schema_description(prefix: str) -> str:
    p = prefix.upper()
    return textwrap.dedent(
        f"""
        You are an expert Oracle SQL generator.

        The user asks questions about a restaurant schema.
        Use ONLY these tables (they are in the current user schema; no schema prefix like SH.):

           {p}_RESTAURANT(
              id, name, image_url,
              address_line1, address_line2, city, state, country, postal_code,
              latitude, longitude, phone,
              created_at, updated_at
            )
           {p}_MENU_ITEM(
              id, restaurant_id, name, image_url,
              description, category, price, currency, available,
              created_at, updated_at
            )

        Join:
          {p}_MENU_ITEM.restaurant_id = {p}_RESTAURANT.id

        Rules:
        - Return VALID ORACLE SQL only.
        - Output MUST be a single SELECT statement (CTEs allowed) and MUST NOT modify data.
        - Do NOT use INSERT/UPDATE/DELETE/MERGE/DDL/PLSQL.
        - Prefer FETCH FIRST N ROWS ONLY for limiting.
        - Do NOT wrap SQL in backticks or markdown fences.
        """
    ).strip()


def _few_shot_examples(prefix: str) -> list[dict[str, str]]:
    p = prefix.upper()
    return [
        {
            "q": "Show all restaurants with their city and image URL.",
            "sql": f"SELECT id, name, city, state, country, image_url FROM {p}_RESTAURANT ORDER BY id FETCH FIRST 20 ROWS ONLY",
        },
        {
            "q": "What menu items are available at Sunrise Bistro?",
            "sql": (
                f"SELECT r.name AS restaurant_name, mi.name AS item_name, mi.category, mi.price, mi.currency, mi.available, mi.image_url\n"
                f"FROM {p}_MENU_ITEM mi JOIN {p}_RESTAURANT r ON r.id = mi.restaurant_id\n"
                f"WHERE LOWER(r.name) = 'sunrise bistro' AND mi.available = 'Y'\n"
                f"ORDER BY mi.category, mi.name FETCH FIRST 50 ROWS ONLY"
            ),
        },
        {
            "q": "Find restaurants near San Francisco.",
            "sql": f"SELECT id, name, address_line1, city, state, latitude, longitude FROM {p}_RESTAURANT WHERE LOWER(city) = 'san francisco' ORDER BY name",
        },
        {
            "q": "Show the cheapest 5 menu items across all restaurants.",
            "sql": (
                f"SELECT r.name AS restaurant_name, mi.name AS item_name, mi.price, mi.currency, mi.image_url\n"
                f"FROM {p}_MENU_ITEM mi JOIN {p}_RESTAURANT r ON r.id = mi.restaurant_id\n"
                f"WHERE mi.available = 'Y'\n"
                f"ORDER BY mi.price ASC NULLS LAST FETCH FIRST 5 ROWS ONLY"
            ),
        },
        {
            "q": "What type of cuisine does Spice Route Kitchen offer?",
            "sql": (
                f"SELECT r.name AS restaurant_name, LISTAGG(DISTINCT mi.category, ', ') WITHIN GROUP (ORDER BY mi.category) AS cuisine_categories\n"
                f"FROM {p}_RESTAURANT r\n"
                f"JOIN {p}_MENU_ITEM mi ON mi.restaurant_id = r.id\n"
                f"WHERE LOWER(r.name) = 'spice route kitchen'\n"
                f"GROUP BY r.name"
            ),
        },
        {
            "q": "What cuisines are available in Los Angeles?",
            "sql": (
                f"SELECT LISTAGG(DISTINCT mi.category, ', ') WITHIN GROUP (ORDER BY mi.category) AS cuisines\n"
                f"FROM {p}_RESTAURANT r\n"
                f"JOIN {p}_MENU_ITEM mi ON mi.restaurant_id = r.id\n"
                f"WHERE LOWER(r.city) = 'los angeles'"
            ),
        },
    ]


def _strip_code_fences(sql: str) -> str:
    s = (sql or "").strip()
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    return s.strip().rstrip(";")


def _is_safe_select_only(sql: str) -> bool:
    s = re.sub(r"\s+", " ", (sql or "").strip()).lower()
    if not s:
        return False
    if not (s.startswith("select ") or s.startswith("with ")):
        return False
    banned = ["insert ", "update ", "delete ", "merge ", "drop ", "alter ", "create ", "truncate ", "begin ", "declare ", "commit", "rollback", "grant ", "revoke "]
    return not any(b in s for b in banned)

@tool()
async def nl2sql_tool(question: str) -> str:
    """Provides natural language to SQL translation using GenAI and executes against DB."""
    llm_client = GenAIProvider().build_oci_client(model_id="xai.grok-4-fast-non-reasoning")
    
    db_conn = RAGDBConnection()
    prefix = db_conn.table_prefix
    schema_description = _build_schema_description(prefix)
    examples = _few_shot_examples(prefix)

    system_content = f"{schema_description}\n\n" + "\n\n".join(
        f"Q: {ex['q']}\nSQL:\n{ex['sql']}" for ex in examples
    )
    
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=question)
    ]
    
    try:
        response = await llm_client.ainvoke(messages)
        generated_sql = _strip_code_fences(str(response.content))

        if not _is_safe_select_only(generated_sql):
            return (
                "Refused to execute generated SQL (only SELECT is allowed).\n"
                "Generated SQL was:\n" + generated_sql
            )
        
        with db_conn.get_connection() as conn:
            cols, rows = db_conn.execute_query(conn, generated_sql)
        
        if not rows:
            return "Query executed successfully but returned no results."
        
        cols_l = [str(c).lower() for c in cols]

        def _get(row_tuple, name: str):
            try:
                idx = cols_l.index(name)
            except ValueError:
                return None
            return row_tuple[idx]

        def _md_image(url: str | None, alt: str) -> str:
            u = (str(url) if url is not None else "").strip()
            if not u:
                return ""
            return f"![{alt}]({u})\n\n"

        lines: list[str] = []
        for row in rows:
            restaurant_name = _get(row, "restaurant_name") or _get(row, "name")
            item_name = _get(row, "item_name")
            image_url = _get(row, "image_url")
            city = _get(row, "city")
            address_line1 = _get(row, "address_line1")
            state = _get(row, "state")
            country = _get(row, "country")
            latitude = _get(row, "latitude")
            longitude = _get(row, "longitude")

            if restaurant_name and (
                "address_line1" in cols_l or "city" in cols_l or "latitude" in cols_l
            ):
                lines.append(f"### {restaurant_name}")
                if address_line1 or city or state or country:
                    addr_parts = [
                        p
                        for p in [address_line1, city, state, country]
                        if p not in (None, "")
                    ]
                    if addr_parts:
                        lines.append(
                            f"Address: {', '.join(str(p) for p in addr_parts)}"
                        )
                if latitude is not None and longitude is not None:
                    lines.append(f"Coordinates: Latitude {latitude}, Longitude {longitude}")
                if image_url:
                    lines.append("")
                    lines.append(_md_image(image_url, str(restaurant_name)).rstrip())
                continue

            if restaurant_name or item_name:
                title = str(item_name or restaurant_name)
                lines.append(f"### {title}")
                if restaurant_name and item_name:
                    lines.append(f"Restaurant: {restaurant_name}")
                category = _get(row, "category")
                price = _get(row, "price")
                currency = _get(row, "currency")
                if category not in (None, ""):
                    lines.append(f"Category: {category}")
                if price not in (None, ""):
                    lines.append(f"Price: {price} {currency or ''}".rstrip())
                if image_url:
                    lines.append("")
                    lines.append(_md_image(image_url, title).rstrip())
                continue

            lines.append(", ".join(f"{col}: {val}" for col, val in zip(cols, row)))

        return "\n".join(lines).strip()
    except Exception as e:
        return f"Error executing NL2SQL: {str(e)}"