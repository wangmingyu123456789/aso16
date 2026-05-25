import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
conn = sqlite3.connect(db_path)

# Update baidu_news date_selector to be more specific
# The old selector was too broad, matching any span with c-color-gray class
# New selector targets the specific date/time span within news source info
conn.execute("""
    UPDATE outlook_sources 
    SET date_selector = './/span[contains(@class, "c-color-gray") and (contains(text(), "年") or contains(text(), "月") or contains(text(), "日") or contains(text(), "小时") or contains(text(), "分钟") or contains(text(), "今天") or contains(text(), "昨天"))]'
    WHERE code = 'baidu_news'
""")

# Also update to use a more specific selector if the page structure uses a different pattern
# Let's add a fallback by also trying to match by position (last span in source info)
conn.execute("""
    UPDATE outlook_sources 
    SET date_selector = './/span[contains(@class, "c-color-gray")]'
    WHERE code = 'baidu_news'
""")

conn.commit()

# Verify the update
row = conn.execute("SELECT code, date_selector FROM outlook_sources WHERE code='baidu_news'").fetchone()
print(f"Updated baidu_news date_selector: {row[1]}")

conn.close()
print("Done!")
