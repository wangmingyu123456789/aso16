import sqlite3

DB_PATH = 'database/app.db'

print("=== 删除前 ===")
conn = sqlite3.connect(DB_PATH)
rows = conn.execute("SELECT id, group_id, content, is_active FROM group_announcements").fetchall()
for r in rows:
    print(f"  id={r[0]}, group_id={r[1]}, content='{r[2]}', is_active={r[3]}")

# 删除前两条
delete_ids = [1, 2]
for ann_id in delete_ids:
    print(f"\n--- 删除 id={ann_id} ---")
    cursor = conn.execute("DELETE FROM group_announcements WHERE id=?", (ann_id,))
    print(f"  rowcount={cursor.rowcount}")
    conn.commit()

print("\n=== 删除后 ===")
rows = conn.execute("SELECT id, group_id, content, is_active FROM group_announcements").fetchall()
for r in rows:
    print(f"  id={r[0]}, group_id={r[1]}, content='{r[2]}', is_active={r[3]}")

conn.close()
print("\n完成")
