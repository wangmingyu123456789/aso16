import httpx
import json
import os
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')

# 先测试百度新闻页面结构
url = "https://www.baidu.com/s?tn=news&word=AI&pn=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

print("Fetching baidu news page...")
resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
print(f"Status: {resp.status_code}")

try:
    from lxml import html as lxml_html
    doc = lxml_html.fromstring(resp.text)
    
    # 查找包含日期的元素
    print("\n=== Searching for date elements ===")
    
    # 尝试多种日期选择器
    selectors = [
        '//span[contains(@class, "c-color-gray")]',
        '//span[contains(@class, "c-color-gray2")]',
        '//span[contains(@class, "time")]',
        '//span[contains(@class, "date")]',
        '//span[contains(@class, "c-span-last")]',
        '//div[contains(@class, "news-source")]',
        '//span[contains(@class, "c-abstract")]',
    ]
    
    for sel in selectors:
        nodes = doc.xpath(sel)
        if nodes:
            print(f"\nSelector: {sel} -> Found {len(nodes)} elements")
            for i, node in enumerate(nodes[:3]):
                text = node.text_content().strip()[:50]
                print(f"  [{i}] '{text}'")
        else:
            print(f"\nSelector: {sel} -> Not found")
    
    # 查看新闻列表项结构
    print("\n=== News item structure ===")
    items = doc.xpath('//div[contains(@class, "result") or contains(@class, "news-item") or contains(@class, "c-container")]')
    if not items:
        items = doc.xpath('//div[@class="result"] | //div[contains(@class, "news_")]')
    
    print(f"Found {len(items)} news items")
    if items:
        item = items[0]
        print(f"\nFirst item HTML structure:")
        spans = item.xpath('.//span')
        for i, span in enumerate(spans[:5]):
            classes = span.get('class', '')
            text = span.text_content().strip()[:50]
            print(f"  span[{i}] class='{classes}' text='{text}'")
        
        # 查看完整HTML
        print(f"\nFirst item full HTML (truncated):")
        print(lxml_html.tostring(item, encoding='unicode')[:500])

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
