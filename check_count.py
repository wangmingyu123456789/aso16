import sqlite3
import os

db_path = os.path.join('database', 'app.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# 查询 outlook_data 表实际记录数
row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data").fetchone()
data_count = row['cnt']
print(f"outlook_data 表实际记录数: {data_count}")

# 查询 outlook_tasks 表的 total_count 总和
row = conn.execute("SELECT SUM(total_count) as total FROM outlook_tasks").fetchone()
tasks_total = row['total'] or 0
print(f"outlook_tasks.total_count 总和: {tasks_total}")

# 查询 outlook_tasks 表的任务数
row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_tasks").fetchone()
task_count = row['cnt']
print(f"outlook_tasks 任务数: {task_count}")

# 查看每个任务的 total_count
rows = conn.execute("SELECT id, keyword, total_count FROM outlook_tasks ORDER BY id").fetchall()
print("\n各任务详情:")
for r in rows:
    print(f"  任务{r['id']}: keyword={r['keyword']}, total_count={r['total_count']}")

print(f"\n=== 数据库真实数据总量 ===")
print(f"  outlook_data 表: {data_count} 条")
print(f"  outlook_tasks total_count 总和: {tasks_total} 条")
print(f"  差异: {data_count - tasks_total} 条")

conn.close()
