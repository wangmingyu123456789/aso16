import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, name, code, date_selector, entry_url FROM outlook_sources ORDER BY id").fetchall()

print(f"Found {len(rows)} sources:")
for r in rows:
    print(f"  ID={r['id']}, Name={r['name']}, Code={r['code']}, date_selector='{r['date_selector']}', url={r['entry_url']}")

conn.close()
