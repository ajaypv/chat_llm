import textwrap
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage
from langchain.tools import tool

from core.gen_ai_provider import GenAIProvider
from database.connections import RAGDBConnection

SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    You are an expert Oracle SQL generator. The user asks questions about
    the SH (Sales History) schema which contains:

      • COUNTRIES(country_id, country_name, region_id)
      • CUSTOMERS(cust_id, cust_first_name, cust_last_name, cust_gender,
                  cust_year_of_birth, country_id, cust_income_level)
      • PRODUCTS(prod_id, prod_name, prod_category, prod_subcategory)
      • CHANNELS(channel_id, channel_desc)
      • TIMES(time_id, calendar_year, calendar_month_desc, calendar_date)
      • SALES(prod_id, cust_id, time_id, channel_id, quantity_sold, amount_sold)

    Joins:
      CUSTOMERS.country_id = COUNTRIES.country_id
      SALES.cust_id        = CUSTOMERS.cust_id
      SALES.prod_id        = PRODUCTS.prod_id
      SALES.channel_id     = CHANNELS.channel_id
      SALES.time_id        = TIMES.time_id

    Always prefix tables with SH. Return valid SQL only. Your output will be directly fed to the oracle database.
    dont include backquotes as they would interfere
    """
)

FEW_SHOT_EXAMPLES = [
    {
        "q": "How many customers are there?",
        "sql": "SELECT COUNT(*) AS customer_cnt FROM SH.CUSTOMERS;",
    },
    {
        "q": "Total amount sold in 1999?",
        "sql": (
            "SELECT SUM(amount_sold) AS total_amount\n"
            "FROM SH.SALES s JOIN SH.TIMES t ON s.time_id = t.time_id\n"
            "WHERE t.calendar_year = 1999;"
        ),
    },
    {
        "q": "Top 3 products by quantity sold in 2000",
        "sql": (
            "SELECT p.prod_name, SUM(quantity_sold) qty\n"
            "FROM SH.SALES s JOIN SH.PRODUCTS p ON s.prod_id = p.prod_id\n"
            "JOIN SH.TIMES t ON s.time_id = t.time_id\n"
            "WHERE t.calendar_year = 2000\n"
            "GROUP BY p.prod_name\n"
            "ORDER BY qty DESC FETCH FIRST 3 ROWS ONLY;"
        ),
    },
]

@tool()
async def nl2sql_tool(question: str) -> str:
    """Provides natural language to SQL translation using GenAI and executes against DB."""
    llm_client = GenAIProvider().build_oci_client(model_id="xai.grok-4-fast-non-reasoning")
    
    system_content = f"{SCHEMA_DESCRIPTION}\n\n" + "\n\n".join(
        f"Q: {ex['q']}\nSQL:\n{ex['sql']}" for ex in FEW_SHOT_EXAMPLES
    )
    
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=question)
    ]
    
    db_conn = RAGDBConnection()
    
    try:
        response = await llm_client.ainvoke(messages)
        generated_sql = response.content.strip()
        
        if generated_sql.startswith("```"):
            lines = generated_sql.split("\n")
            generated_sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        with db_conn.get_connection() as conn:
            cols, rows = db_conn.execute_query(conn, generated_sql)
        
        if not rows:
            return "Query executed successfully but returned no results."
        
        result_lines = []
        for row in rows:
            row_data = ", ".join(f"{col}: {val}" for col, val in zip(cols, row))
            result_lines.append(row_data)
        
        return f"Query Results:\n" + "\n".join(result_lines)
    except Exception as e:
        return f"Error executing NL2SQL: {str(e)}"