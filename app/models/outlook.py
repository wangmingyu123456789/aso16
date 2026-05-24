import json
import time
import httpx
import re
from urllib.parse import quote
from app.models.db import get_connection
from app.models.model import ModelRepository

try:
    from lxml import html as lxml_html
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


class OutlookSourceRepository:
    @staticmethod
    def get_all_sources():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM outlook_sources ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_active_sources():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM outlook_sources WHERE status=1 ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_source_by_id(source_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM outlook_sources WHERE id=?", (source_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_source(name, code, entry_url, method='GET', request_headers='', parser_type='html',
                     html_selector='', title_selector='', url_selector='', content_selector='',
                     date_selector='', author_selector='', page_size_step=10, page_start=0,
                     ai_expand_keyword=0, ai_expand_prompt='', ai_clean_data=0, ai_clean_prompt='',
                     status=1, description=''):
        try:
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO outlook_sources(name,code,entry_url,method,request_headers,parser_type,
                       html_selector,title_selector,url_selector,content_selector,date_selector,author_selector,
                       page_size_step,page_start,ai_expand_keyword,ai_expand_prompt,ai_clean_data,ai_clean_prompt,
                       status,description) 
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, code, entry_url, method, request_headers, parser_type,
                     html_selector, title_selector, url_selector, content_selector,
                     date_selector, author_selector, page_size_step, page_start,
                     ai_expand_keyword, ai_expand_prompt, ai_clean_data, ai_clean_prompt,
                     status, description)
                )
                return True
        except Exception:
            return False

    @staticmethod
    def update_source(source_id, name=None, code=None, entry_url=None, method=None, request_headers=None,
                     parser_type=None, html_selector=None, title_selector=None, url_selector=None,
                     content_selector=None, date_selector=None, author_selector=None,
                     page_size_step=None, page_start=None, ai_expand_keyword=None, ai_expand_prompt=None,
                     ai_clean_data=None, ai_clean_prompt=None, status=None, description=None):
        updates = []
        params = []
        fields = {
            'name': name, 'code': code, 'entry_url': entry_url, 'method': method,
            'request_headers': request_headers, 'parser_type': parser_type,
            'html_selector': html_selector, 'title_selector': title_selector,
            'url_selector': url_selector, 'content_selector': content_selector,
            'date_selector': date_selector, 'author_selector': author_selector,
            'page_size_step': page_size_step, 'page_start': page_start,
            'ai_expand_keyword': ai_expand_keyword, 'ai_expand_prompt': ai_expand_prompt,
            'ai_clean_data': ai_clean_data, 'ai_clean_prompt': ai_clean_prompt,
            'status': status, 'description': description
        }
        for field, value in fields.items():
            if value is not None:
                updates.append(f"{field}=?")
                params.append(value)
        if not updates:
            return False
        params.append(source_id)
        try:
            with get_connection() as conn:
                conn.execute(
                    f"UPDATE outlook_sources SET {','.join(updates)} WHERE id=?",
                    params
                )
                return True
        except Exception:
            return False

    @staticmethod
    def delete_source(source_id):
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM outlook_sources WHERE id=?", (source_id,))
                return True
        except Exception:
            return False


class OutlookDataRepository:
    @staticmethod
    def get_data_list(page=1, page_size=20, keyword=None):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                count_row = conn.execute(
                    "SELECT COUNT(*) as total FROM outlook_data WHERE title LIKE ?",
                    (f'%{keyword}%',)
                ).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data WHERE title LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (f'%{keyword}%', page_size, offset)
                ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) as total FROM outlook_data").fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data ORDER BY id DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
        return {
            'total': total,
            'data': [dict(row) for row in rows],
            'page': page,
            'page_size': page_size
        }

    @staticmethod
    def save_data(source_id, source_name, title, url='', content='', author='', publish_date='', raw_html='', ai_processed=0):
        try:
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO outlook_data(source_id,source_name,title,url,content,author,publish_date,raw_html,ai_processed) 
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (source_id, source_name, title, url, content, author, publish_date, raw_html, ai_processed)
                )
                return True
        except Exception:
            return False

    @staticmethod
    def delete_data(data_id):
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM outlook_data WHERE id=?", (data_id,))
                return True
        except Exception:
            return False

    @staticmethod
    def delete_data_batch(data_ids):
        try:
            with get_connection() as conn:
                conn.execute(
                    f"DELETE FROM outlook_data WHERE id IN ({','.join(['?']*len(data_ids))})",
                    data_ids
                )
                return True
        except Exception:
            return False


class OutlookCollector:
    @staticmethod
    def create_session(custom_headers_json=''):
        """
        创建可复用的 httpx session，自动管理 Cookie。
        先访问百度首页获取初始 Cookie，再进行后续请求。
        """
        default_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
            "Referer": "https://www.baidu.com/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        custom_cookies = None
        if custom_headers_json:
            try:
                custom = json.loads(custom_headers_json)
                cookie_str = custom.pop('Cookie', '') or custom.pop('cookie', '')
                if cookie_str:
                    custom_cookies = {}
                    for pair in cookie_str.split(';'):
                        pair = pair.strip()
                        if not pair or '=' not in pair:
                            continue
                        k, v = pair.split('=', 1)
                        k = k.strip()
                        v = v.strip()
                        if k:
                            custom_cookies[k] = v
                custom.pop('Host', None)
                custom.pop('host', None)
                custom.pop('Accept-Encoding', None)
                custom.pop('accept-encoding', None)
                default_headers.update(custom)
            except Exception as e:
                print(f"[Session] Failed to parse custom headers: {e}")

        session = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
            cookies=custom_cookies,
            headers=default_headers,
        )

        if not custom_cookies:
            try:
                session.get("https://www.baidu.com/", headers={"User-Agent": default_headers["User-Agent"]})
                cookie_names = list(session.cookies.keys()) if session.cookies else []
                print(f"[Session] Auto-acquired cookies: {cookie_names}")
            except Exception as e:
                print(f"[Session] Failed to acquire cookies from baidu.com: {e}")

        return session

    @staticmethod
    def fetch_page(session, url, method='GET', body=''):
        t0 = time.time()
        try:
            if method.upper() == 'POST':
                response = session.post(url, data=body)
            else:
                response = session.get(url)

            t1 = time.time()
            try:
                import chardet
                detected = chardet.detect(response.content)
                if detected and detected.get('encoding'):
                    response.encoding = detected['encoding']
            except ImportError:
                response.encoding = 'utf-8'

            elapsed = round(t1 - t0, 2)
            cookie_count = len(session.cookies) if session.cookies else 0
            print(f"[Fetch] HTTP {response.status_code}, {len(response.text)} bytes, {elapsed}s, session_cookies={cookie_count}")
            return response.status_code, response.text
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"[Fetch] ERROR after {elapsed}s: {type(e).__name__}: {e}")
            return 0, str(e)

    @staticmethod
    def build_url(entry_url, keyword, page_num, page_size_step=10, page_start=0):
        page_val = page_start + page_num * page_size_step
        url = entry_url.replace('{keyword}', quote(keyword, safe='')).replace('{page}', str(page_val))
        url = url.replace('{page_start}', str(page_start)).replace('{page_size_step}', str(page_size_step))
        return url

    @staticmethod
    def expand_keywords_with_ai(keyword, prompt=''):
        if not prompt:
            prompt = f'请为关键词"{keyword}"生成5个相关的搜索关键词，用于扩展数据采集范围。每个关键词用逗号分隔，不要输出其他内容。'

        t0 = time.time()
        try:
            model_config = ModelRepository.get_default_model()
            if not model_config:
                print(f"[AI-Expand] No default model, skip expansion for: {keyword}")
                return [keyword]

            messages = [{"role": "user", "content": prompt}]
            response_text = ModelRepository.call_model_api(
                model_config['api_url'],
                model_config['api_key'],
                model_config.get('code', 'default'),
                messages,
                temperature=0.7,
                max_tokens=500
            )
            elapsed = round(time.time() - t0, 2)

            if response_text:
                expanded = re.split(r'[,，、\n]', response_text.strip())
                expanded = [k.strip() for k in expanded if k.strip()]
                print(f"[AI-Expand] '{keyword}' -> {len(expanded)} keywords in {elapsed}s: {expanded}")
                return expanded if expanded else [keyword]
            else:
                print(f"[AI-Expand] Empty response from model in {elapsed}s, fallback to original: {keyword}")
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"[AI-Expand] ERROR in {elapsed}s: {type(e).__name__}: {e}")

        return [keyword]

    @staticmethod
    def clean_data_with_ai(raw_items, prompt=''):
        if not prompt:
            print(f"[AI-Clean] No prompt provided, skip cleaning")
            return raw_items

        items_text = json.dumps(raw_items, ensure_ascii=False, indent=2)
        full_prompt = f"以下是采集到的原始数据：\n{items_text}\n\n处理要求：\n{prompt}\n\n请直接返回JSON数组，不要其他内容。"

        t0 = time.time()
        try:
            model_config = ModelRepository.get_default_model()
            if not model_config:
                print(f"[AI-Clean] No default model, skip cleaning for {len(raw_items)} items")
                return raw_items

            messages = [{"role": "user", "content": full_prompt}]
            response_text = ModelRepository.call_model_api(
                model_config['api_url'],
                model_config['api_key'],
                model_config.get('code', 'default'),
                messages,
                temperature=0.3,
                max_tokens=4000
            )
            elapsed = round(time.time() - t0, 2)

            if response_text:
                cleaned_json = re.findall(r'\[.*\]', response_text, re.DOTALL)
                if cleaned_json:
                    cleaned = json.loads(cleaned_json[0])
                    print(f"[AI-Clean] {len(raw_items)} raw items -> {len(cleaned)} cleaned items in {elapsed}s")
                    return cleaned
                else:
                    print(f"[AI-Clean] No JSON array found in response in {elapsed}s, return raw data")
            else:
                print(f"[AI-Clean] Empty response from model in {elapsed}s")
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"[AI-Clean] ERROR in {elapsed}s: {type(e).__name__}: {e}")

        return raw_items

    @staticmethod
    def parse_html(html_content, html_selector, title_selector, url_selector, content_selector, date_selector, author_selector):
        if not HAS_LXML:
            return []

        try:
            doc = lxml_html.fromstring(html_content)
        except Exception:
            return []

        items = []
        if html_selector:
            nodes = doc.xpath(html_selector)
        else:
            nodes = [doc]

        for node in nodes:
            item = {}

            if title_selector:
                title_nodes = node.xpath(title_selector)
                if title_nodes:
                    title_node = title_nodes[0]
                    item['title'] = title_node.text_content().strip()
                    if url_selector:
                        if 'href' in title_node.attrib:
                            item['url'] = title_node.attrib['href']
                        else:
                            a_nodes = title_node.xpath('.//a')
                            if a_nodes and 'href' in a_nodes[0].attrib:
                                item['url'] = a_nodes[0].attrib['href']
                else:
                    continue
            else:
                continue

            if url_selector and 'url' not in item:
                url_nodes = node.xpath(url_selector)
                if url_nodes and 'href' in url_nodes[0].attrib:
                    item['url'] = url_nodes[0].attrib['href']

            if content_selector:
                content_nodes = node.xpath(content_selector)
                if content_nodes:
                    item['content'] = content_nodes[0].text_content().strip()

            if date_selector:
                date_nodes = node.xpath(date_selector)
                if date_nodes:
                    item['publish_date'] = date_nodes[0].text_content().strip()

            if author_selector:
                author_nodes = node.xpath(author_selector)
                if author_nodes:
                    item['author'] = author_nodes[0].text_content().strip()

            if item.get('title'):
                items.append(item)

        return items

    @staticmethod
    def collect(source, keyword, pages=1, page_size_step=10, use_ai_expand=False, use_ai_clean=False):
        t_start = time.time()
        print(f"\n{'='*60}")
        print(f"[Collect] START: source={source['name']} ({source['code']}), keyword={keyword}")
        print(f"[Collect] Config: pages={pages}, step={page_size_step}, ai_expand={use_ai_expand}, ai_clean={use_ai_clean}")
        print(f"{'='*60}")

        all_results = []
        keywords = [keyword]

        # Step 1: AI keyword expansion
        if use_ai_expand or source.get('ai_expand_keyword', 0):
            t_exp = time.time()
            keywords = OutlookCollector.expand_keywords_with_ai(
                keyword, source.get('ai_expand_prompt', '')
            )
            t_exp_elapsed = round(time.time() - t_exp, 2)
            print(f"[Collect] Step 1: AI keyword expansion completed in {t_exp_elapsed}s, {len(keywords)} keywords")

        page_start = source.get('page_start', 0)
        page_fetch_times = []
        page_parse_counts = []

        # Step 2: Fetch and parse pages
        session = OutlookCollector.create_session(source.get('request_headers', ''))

        total_urls = len(keywords) * pages
        url_idx = 0
        for kw in keywords:
            for page_num in range(pages):
                url_idx += 1
                url = OutlookCollector.build_url(
                    source['entry_url'], kw, page_num, page_size_step, page_start
                )
                print(f"[Collect] Step 2.{url_idx}/{total_urls}: keyword='{kw}', page={page_num+1}/{pages}")
                print(f"[Collect]   URL: {url}")

                t_fetch = time.time()
                status_code, html_content = OutlookCollector.fetch_page(
                    session,
                    url,
                    source.get('method', 'GET'),
                    source.get('body_template', '')
                )
                t_fetch_elapsed = round(time.time() - t_fetch, 2)
                page_fetch_times.append(t_fetch_elapsed)

                if status_code != 200:
                    print(f"[Collect]   SKIP: HTTP {status_code}, error={html_content[:100]}")
                    page_parse_counts.append(0)
                    continue

                # Check captcha
                if '验证码' in html_content or 'captcha' in html_content.lower():
                    print(f"[Collect]   SKIP: Captcha detected")
                    page_parse_counts.append(0)
                    continue

                # Parse HTML
                t_parse = time.time()
                items = OutlookCollector.parse_html(
                    html_content,
                    source.get('html_selector', ''),
                    source.get('title_selector', ''),
                    source.get('url_selector', ''),
                    source.get('content_selector', ''),
                    source.get('date_selector', ''),
                    source.get('author_selector', '')
                )
                t_parse_elapsed = round(time.time() - t_parse, 2)
                page_parse_counts.append(len(items))
                print(f"[Collect]   Parse: {len(items)} items in {t_parse_elapsed}s")

                # Show first 2 items as preview
                for idx, item in enumerate(items[:2]):
                    print(f"[Collect]     Item {idx+1}: title='{item.get('title', '')[:60]}', date='{item.get('publish_date', '')}'")
                if len(items) > 2:
                    print(f"[Collect]     ... and {len(items) - 2} more items")

                for item in items:
                    item['source_keyword'] = kw
                    all_results.append(item)

        # Step 3: AI data cleaning
        if use_ai_clean or source.get('ai_clean_data', 0):
            t_clean = time.time()
            ai_prompt = source.get('ai_clean_prompt', '')
            if ai_prompt:
                all_results = OutlookCollector.clean_data_with_ai(all_results, ai_prompt)
            t_clean_elapsed = round(time.time() - t_clean, 2)
            print(f"[Collect] Step 3: AI data cleaning completed in {t_clean_elapsed}s, {len(all_results)} items")

        # Step 4: Save to database
        t_save = time.time()
        saved_count = 0
        for item in all_results:
            if isinstance(item, dict):
                ai_processed = 1 if (use_ai_clean or source.get('ai_clean_data', 0)) else 0
                saved = OutlookDataRepository.save_data(
                    source_id=source['id'],
                    source_name=source['name'],
                    title=item.get('title', ''),
                    url=item.get('url', ''),
                    content=item.get('content', ''),
                    author=item.get('author', ''),
                    publish_date=item.get('publish_date', ''),
                    raw_html='',
                    ai_processed=ai_processed
                )
                if saved:
                    saved_count += 1
        t_save_elapsed = round(time.time() - t_save, 2)

        t_total = round(time.time() - t_start, 2)
        avg_fetch = round(sum(page_fetch_times) / len(page_fetch_times), 2) if page_fetch_times else 0
        total_parsed = sum(page_parse_counts)

        print(f"[Collect] Step 4: Save {saved_count}/{len(all_results)} items to DB in {t_save_elapsed}s")
        print(f"[Collect] SUMMARY: total_urls={total_urls}, fetch_times={page_fetch_times}, avg_fetch={avg_fetch}s")
        print(f"[Collect] SUMMARY: parse_counts={page_parse_counts}, total_parsed={total_parsed}, saved={saved_count}")
        print(f"[Collect] TOTAL TIME: {t_total}s")
        print(f"{'='*60}\n")

        session.close()
        return saved_count
