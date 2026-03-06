from database.connections import RAGDBConnection


def main() -> int:
    db = RAGDBConnection()
    with db.get_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT category, COUNT(*) FROM {}_knowledge_file GROUP BY category ORDER BY category".format(
                db.table_prefix
            )
        )
        print("categories in {}_knowledge_file:".format(db.table_prefix))
        for row in cur.fetchall() or []:
            print("  {} -> {}".format(row[0], row[1]))

        cur.execute(
            "SELECT COUNT(*) FROM {}_embedding".format(db.table_prefix)
        )
        total_embeddings = int(cur.fetchone()[0])
        print("total rows in {}_embedding: {}".format(db.table_prefix, total_embeddings))

        cur.execute(
            "SELECT source, COUNT(*) FROM {}_embedding GROUP BY source ORDER BY COUNT(*) DESC FETCH FIRST 10 ROWS ONLY".format(
                db.table_prefix
            )
        )
        print("top embedding sources:")
        for row in cur.fetchall() or []:
            print("  {} -> {}".format(row[0], row[1]))

        # Check joinability: how many embedding rows have a matching knowledge_file.
        cur.execute(
            """
            SELECT COUNT(*)
            FROM {p}_embedding e
            WHERE EXISTS (
              SELECT 1 FROM {p}_knowledge_file f
              WHERE f.storage_path = e.source
            )
            """.format(p=db.table_prefix)
        )
        joined = int(cur.fetchone()[0])
        print("embeddings that join to knowledge_file via storage_path==source: {}".format(joined))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
