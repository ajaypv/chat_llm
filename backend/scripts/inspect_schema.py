import argparse
import os

from dotenv import load_dotenv

from database.connections import RAGDBConnection


def _yn(flag):
    return "Y" if flag == "Y" else "N"


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Inspect Oracle schema: list tables and their columns."
    )
    parser.add_argument(
        "--owner",
        default=(os.getenv("DB_OWNER") or os.getenv("DB_USERNAME") or os.getenv("DB_USER")),
        help="Schema owner to inspect (default: DB_OWNER or DB_USERNAME).",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("DB_TABLE_PREFIX") or "",
        help="Optional table prefix filter (default: DB_TABLE_PREFIX).",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include all tables you can see (ignore prefix filter).",
    )
    args = parser.parse_args()

    owner = (args.owner or "").upper()
    prefix = (args.prefix or "").upper()

    db = RAGDBConnection()
    with db.get_connection() as conn:
        if args.include_all or not prefix:
            tables_sql = (
                "SELECT owner, table_name "
                "FROM all_tables "
                "WHERE (:owner IS NULL OR owner = :owner) "
                "ORDER BY owner, table_name"
            )
            bind_owner = owner if owner else None
            with conn.cursor() as cur:
                cur.execute(tables_sql, owner=bind_owner)
                tables = cur.fetchall()
        else:
            tables_sql = (
                "SELECT owner, table_name "
                "FROM all_tables "
                "WHERE (:owner IS NULL OR owner = :owner) "
                "AND table_name LIKE :prefix || '%' "
                "ORDER BY owner, table_name"
            )
            bind_owner = owner if owner else None
            with conn.cursor() as cur:
                cur.execute(tables_sql, owner=bind_owner, prefix=prefix)
                tables = cur.fetchall()

        if not tables:
            print(
                "No tables found. Try --include-all or pass --owner/--prefix explicitly."
            )
            return 2

        print("Found {} tables".format(len(tables)))

        cols_sql = (
            "SELECT column_id, column_name, data_type, data_length, data_precision, data_scale, nullable "
            "FROM all_tab_columns "
            "WHERE owner = :owner AND table_name = :table_name "
            "ORDER BY column_id"
        )

        for (tbl_owner, table_name) in tables:
            print("\n" + "=" * 80)
            print("{}.{}".format(tbl_owner, table_name))

            with conn.cursor() as cur:
                cur.execute(cols_sql, owner=tbl_owner, table_name=table_name)
                rows = cur.fetchall()

            if not rows:
                print("  (no columns returned)")
                continue

            for (
                column_id,
                column_name,
                data_type,
                data_length,
                data_precision,
                data_scale,
                nullable,
            ) in rows:
                length_part = ""
                if data_type in {"CHAR", "NCHAR", "VARCHAR2", "NVARCHAR2"} and data_length is not None:
                    length_part = "({})".format(int(data_length))
                elif data_type == "NUMBER" and data_precision is not None:
                    if data_scale is None:
                        length_part = "({})".format(int(data_precision))
                    else:
                        length_part = "({},{})".format(int(data_precision), int(data_scale)))

                null_part = "NULL" if _yn(nullable) == "Y" else "NOT NULL"
                print(
                    "  {cid:>3}  {cname:<32} {dtype}{lpart:<14} {npart}".format(
                        cid=int(column_id),
                        cname=column_name,
                        dtype=data_type,
                        lpart=length_part,
                        npart=null_part,
                    )
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
