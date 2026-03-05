from database.connections import RAGDBConnection

db = RAGDBConnection()
table_name = f"{db.table_prefix.upper()}_EMBEDDING"

conn = db._get_pool().acquire()
cur = conn.cursor()

cur.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
schema = cur.fetchone()[0]

cur.execute(
    "SELECT column_name FROM user_tab_columns WHERE table_name = :1 ORDER BY column_id",
    [table_name],
)

cols = [r[0] for r in cur.fetchall()]

print(f"DB_TABLE_PREFIX: {db.table_prefix}")
print(f"Schema: {schema}")
print(f"Columns in {table_name}:")

if not cols:
    raise SystemExit(
        f"Table {schema}.{table_name} not found (or no columns visible). "
        "Create it via migrations (embedding table migration may be missing)."
    )

for col in cols:
    print(f"  - {col}")

cur.close()
conn.close()
