import os

from dotenv import load_dotenv

from database.connections import RAGDBConnection


def main() -> int:
    load_dotenv()
    db = RAGDBConnection()
    prefix = db.table_prefix

    with db.get_connection() as conn:
        cur = conn.cursor()

        print(f"prefix={prefix}")

        cur.execute(f"SELECT COUNT(*) FROM {prefix}_restaurant")
        rest_count = int(cur.fetchone()[0])
        print(f"{prefix}_restaurant count: {rest_count}")

        cur.execute(
            f"""
            SELECT id, name, image_url, city, state, country
            FROM {prefix}_restaurant
            ORDER BY id
            FETCH FIRST 10 ROWS ONLY
            """
        )
        rows = cur.fetchall()
        print("\nRestaurants:")
        for r in rows:
            print(f"- id={r[0]} name={r[1]} city={r[3]} state={r[4]} country={r[5]}")
            print(f"  image_url={r[2]}")

        cur.execute(f"SELECT COUNT(*) FROM {prefix}_menu_item")
        item_count = int(cur.fetchone()[0])
        print(f"\n{prefix}_menu_item count: {item_count}")

        cur.execute(
            f"""
            SELECT mi.id, r.name, mi.name, mi.category, mi.price, mi.currency, mi.available, mi.image_url
            FROM {prefix}_menu_item mi
            JOIN {prefix}_restaurant r ON r.id = mi.restaurant_id
            ORDER BY mi.id
            FETCH FIRST 20 ROWS ONLY
            """
        )
        rows = cur.fetchall()
        print("\nMenu items:")
        for r in rows:
            print(
                f"- id={r[0]} restaurant={r[1]} item={r[2]} cat={r[3]} price={r[4]} {r[5]} avail={r[6]}\n"
                f"  image_url={r[7]}"
            )

        cur.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
