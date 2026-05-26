import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "app.db")

conn = sqlite3.connect(DB_PATH)

for tid in (17, 18):
    old = conn.execute("SELECT create_at FROM outlook_tasks WHERE id=?", (tid,)).fetchone()
    if old:
        new = conn.execute("SELECT datetime(?, '-8 hours')", (old[0],)).fetchone()[0]
        print(f"task id={tid}: {old[0]} -> {new}")
        conn.execute("UPDATE outlook_tasks SET create_at=? WHERE id=?", (new, tid))

conn.commit()
conn.close()
print("done")
