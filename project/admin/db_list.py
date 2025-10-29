# admin/db_list.py
import sqlite3

from project.core.config import DB_PATH
from project.db.db_init import initialize_database


def pretty_print(rows):
    if not rows:
        print("[DB] Database is empty.")
        return

    headers = ["ID", "Ime i prezime", "Roditelj", "Godina", "Mjesec", "Dan", "Mjesto", "Opština", "Razred", "Struka", "Razlog", "Vrijeme unosa"]
    col_widths = [max(len(str(row[i])) for row in rows + [headers]) + 2 for i in range(len(headers))]

    print("=" * sum(col_widths))
    print("".join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers))))
    print("-" * sum(col_widths))

    for row in rows:
        print("".join(f"{str(row[i]):<{col_widths[i]}}" for i in range(len(headers))))
    print("=" * sum(col_widths))


def list_entries():
    initialize_database()

    # ask user for limit
    try:
        user_input = input("Do you want to limit the number of displayed entries? (yes/no): ").strip().lower()
        if user_input in ("yes", "y"):
            limit_input = input("How many entries do you want to display: ").strip()
            limit = int(limit_input)
            if limit <= 0:
                print("[WARNING] Non-positive number entered, displaying all entries.")
                limit = None
        else:
            limit = None
    except ValueError:
        print("[WARNING] Invalid input, displaying all entries.")
        limit = None
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if limit:
            cursor.execute("""
                SELECT id, ime, roditelj, godina, mjesec, dan, mjesto, opstina, razred, struka, razlog, created_at
                FROM print_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT id, ime, roditelj, godina, mjesec, dan, mjesto, opstina, razred, struka, razlog, created_at
                FROM print_logs
                ORDER BY id DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        pretty_print(rows)

    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")


if __name__ == "__main__":
    list_entries()