"""向现有数据库中添加更多新闻采集源"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.models.db import get_connection

NEW_SOURCES = [
    {
        "name": "搜狗新闻",
        "code": "sogou_news",
        "entry_url": "https://news.sogou.com/news?query={keyword}&page={page}",
        "html_selector": "//div[contains(@class, 'vrwrap')]/div[contains(@class, 'vr')]",
        "title_selector": ".//h3/a",
        "url_selector": ".//h3/a/@href",
        "content_selector": ".//div[contains(@class, 'str-text')]/p",
        "date_selector": ".//div[contains(@class, 'news-time')]/span",
        "page_size_step": 1,
        "page_start": 1,
        "description": "搜狗新闻搜索引擎采集源"
    },
    {
        "name": "360新闻",
        "code": "so_news",
        "entry_url": "https://news.so.com/ns?q={keyword}&pn={page}",
        "html_selector": "//ul[contains(@class, 'result')]/li",
        "title_selector": ".//h3/a",
        "url_selector": ".//h3/a/@href",
        "content_selector": ".//p[contains(@class, 'info')]",
        "date_selector": ".//span[contains(@class, 'time')]",
        "page_size_step": 1,
        "page_start": 1,
        "description": "360新闻搜索引擎采集源"
    },
    {
        "name": "必应新闻",
        "code": "bing_news",
        "entry_url": "https://www.bing.com/news/search?q={keyword}&first={page}",
        "html_selector": "//div[contains(@class, 'news-card')]",
        "title_selector": ".//a[contains(@class, 'title')]",
        "url_selector": ".//a[contains(@class, 'title')]/@href",
        "content_selector": ".//div[contains(@class, 'snippet')]",
        "date_selector": ".//span[contains(@class, 'date')]",
        "page_size_step": 10,
        "page_start": 0,
        "description": "必应新闻搜索引擎采集源"
    },
    {
        "name": "新浪新闻",
        "code": "sina_news",
        "entry_url": "https://search.sina.com.cn/news?q={keyword}&c=news&range=all&time=all&num=20&page={page}",
        "html_selector": "//div[contains(@class, 'result')]",
        "title_selector": ".//h2/a",
        "url_selector": ".//h2/a/@href",
        "content_selector": ".//p[contains(@class, 'content')]",
        "date_selector": ".//span[contains(@class, 'date')]",
        "page_size_step": 1,
        "page_start": 1,
        "description": "新浪新闻搜索引擎采集源"
    },
]

def add_sources():
    added = 0
    skipped = 0
    for src in NEW_SOURCES:
        try:
            with get_connection() as conn:
                exists = conn.execute(
                    "SELECT id FROM outlook_sources WHERE code=?", (src["code"],)
                ).fetchone()
                if exists:
                    print(f"  [跳过] {src['name']} ({src['code']}) 已存在")
                    skipped += 1
                    continue

                conn.execute(
                    """INSERT INTO outlook_sources(
                        name, code, entry_url, method, parser_type,
                        html_selector, title_selector, url_selector,
                        content_selector, date_selector,
                        page_size_step, page_start, status, description
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                    (
                        src["name"], src["code"], src["entry_url"], 'GET', 'html',
                        src["html_selector"], src["title_selector"], src["url_selector"],
                        src["content_selector"], src["date_selector"],
                        src["page_size_step"], src["page_start"], src["description"]
                    )
                )
                print(f"  [新增] {src['name']} ({src['code']})")
                added += 1
        except Exception as e:
            print(f"  [错误] {src['name']}: {e}")
            skipped += 1

    print(f"\n完成！新增 {added} 个，跳过 {skipped} 个")

if __name__ == '__main__':
    print("正在添加新闻采集源...\n")
    add_sources()
    print("\n提示：如果采集时选择器不准确，可在管理后台的采集源管理中修改。")
