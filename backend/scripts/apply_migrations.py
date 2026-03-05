from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from database.connections import RAGDBConnection


def iter_sql_statements(sql_text: str) -> list[str]:
    """Split a migration file into executable statements.

    Supports:
    - Regular SQL statements ending with ';'
    - PL/SQL blocks terminated by a line containing only '/'
    """
    statements: list[str] = []
    buf: list[str] = []
    in_plsql = False

    def flush() -> None:
        nonlocal buf, in_plsql
        text = "\n".join(buf).strip()
        buf = []
        in_plsql = False
        if text:
            statements.append(text)

    for raw in sql_text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("--"):
            continue

        # A single '/' ends a PL/SQL block in SQL*Plus/SQLcl style.
        if stripped == "/":
            flush()
            continue

        if stripped.upper().startswith("DECLARE") or stripped.upper().startswith("BEGIN"):
            in_plsql = True

        # For normal SQL, split on semicolons.
        if not in_plsql and ";" in raw:
            parts = raw.split(";")
            for i, part in enumerate(parts):
                if i < len(parts) - 1:
                    buf.append(part)
                    flush()
                else:
                    if part.strip():
                        buf.append(part)
            continue

        buf.append(raw)

    flush()
    return statements


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Oracle migrations from database/migrations")
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parents[2] / "database" / "migrations"),
        help="Migrations directory (default: <repo>/database/migrations)",
    )
    args = parser.parse_args()

    load_dotenv()

    migrations_dir = Path(args.dir).resolve()
    if not migrations_dir.exists():
        raise SystemExit(f"Migrations dir not found: {migrations_dir}")

    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        print(f"No .sql migrations found in {migrations_dir}")
        return 0

    db = RAGDBConnection()
    prefix = (db.table_prefix or "edge_demo").strip()
    with db.get_connection() as conn:
        for sql_path in sql_files:
            print(f"Applying {sql_path.name} ...")
            sql_text = sql_path.read_text(encoding="utf-8").replace("${PREFIX}", prefix)
            statements = iter_sql_statements(sql_text)
            if not statements:
                print(" - (empty)")
                continue

            with conn.cursor() as cur:
                for idx, stmt in enumerate(statements, start=1):
                    try:
                        cur.execute(stmt)
                    except Exception as e:
                        # Common case: re-running migrations where objects already exist.
                        print(f" - Statement {idx} skipped: {e}")
            conn.commit()
            print(" - done")

    print("All migrations applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
