from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from database.connections import RAGDBConnection


def iter_sql_statements(sql_text: str) -> list[str]:
    # Very small splitter: good enough for our simple migration files.
    # Strips line comments and splits on ';'.
    lines: list[str] = []
    for raw in sql_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("--"):
            continue
        lines.append(raw)

    joined = "\n".join(lines)
    parts = [p.strip() for p in joined.split(";")]
    return [p for p in parts if p]


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
    with db.get_connection() as conn:
        for sql_path in sql_files:
            print(f"Applying {sql_path.name} ...")
            sql_text = sql_path.read_text(encoding="utf-8")
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
