import app.models.db as db

# Run migration
print("Running upgrade_db...")
db.upgrade_db()
print("Done!")

# Verify
import sqlite3
conn = sqlite3.connect(db.DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT id, assistant_name, assistant_code, sort_order FROM assistants ORDER BY sort_order').fetchall()
print("\nAll assistants:")
for r in rows:
    print(f'  {r["id"]}: {r["assistant_name"]} (code={r["assistant_code"]}, sort={r["sort_order"]})')
conn.close()
