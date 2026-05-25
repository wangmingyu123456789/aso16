import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# 查看最近采集的数据
rows = conn.execute("SELECT id, title, author, publish_date, source_keyword, url FROM outlook_data ORDER BY id DESC LIMIT 10").fetchall()

print(f"Latest {len(rows)} data items:")
for r in rows:
    print(f"\nID={r['id']}")
    print(f"  Title: {r['title'][:60]}")
    print(f"  Author: {r['author']}")
    print(f"  Date: {r['publish_date']}")
    print(f"  Keyword: {r['source_keyword']}")
    print(f"  URL: {r['url'][:80]}")

# 统计日期字段情况
total = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data").fetchone()['cnt']
with_date = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data WHERE publish_date IS NOT NULL AND publish_date != ''").fetchone()['cnt']
with_keyword = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data WHERE source_keyword IS NOT NULL AND source_keyword != ''").fetchone()['cnt']
keyword_in_date = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data WHERE publish_date LIKE '%关键词%' OR publish_date LIKE '%搜索%' OR length(publish_date) > 30").fetchone()['cnt']

print(f"\n=== Statistics ===")
print(f"Total items: {total}")
print(f"With date: {with_date} ({with_date/total*100:.1f}%)")
print(f"With keyword: {with_keyword} ({with_keyword/total*100:.1f}%)")
print(f"Keyword in date field: {keyword_in_date}")

conn.close()
