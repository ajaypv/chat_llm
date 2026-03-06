from database.connections import RAGDBConnection

db = RAGDBConnection()

conn = db._get_pool().acquire()
cur = conn.cursor()

cur.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
schema = cur.fetchone()[0]

# Fetch all tables in the current schema.
cur.execute(
    """
    SELECT table_name
    FROM user_tables
    ORDER BY table_name
    """
)
tables = [r[0] for r in cur.fetchall()]

print("DB_TABLE_PREFIX: {}".format(db.table_prefix))
print("Schema: {}".format(schema))
print("Tables found: {}".format(len(tables)))

if not tables:
    raise SystemExit("No tables found in current schema.")

for table_name in tables:
    # If a prefix is configured, only show those tables. Comment out to show all.
    if db.table_prefix and not table_name.startswith(db.table_prefix.upper() + "_"):
        continue

    cur.execute(
        """
        SELECT column_id, column_name, data_type, nullable
        FROM user_tab_columns
        WHERE table_name = :1
        ORDER BY column_id
        """,
        [table_name],
    )
    cols = cur.fetchall()

    print("\n" + "=" * 80)
    print("{}.{}".format(schema, table_name))

    if not cols:
        print("  (no columns visible)")
        continue

    for col_id, col_name, data_type, nullable in cols:
        null_part = "NULL" if nullable == "Y" else "NOT NULL"
        print("  {cid:>3}  {cname:<32} {dtype:<12} {null}".format(
            cid=int(col_id), cname=col_name, dtype=data_type, null=null_part
        ))

cur.close()
conn.close()
