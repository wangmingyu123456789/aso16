import json
import time
import httpx
import re
import random
import asyncio
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
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


class OutlookTaskRepository:
    @staticmethod
    def create_task(keyword, source_ids, source_names, pages, page_size_step, ai_expand, ai_clean):
        """
        创建新的采集任务
        """
        import datetime
        create_at = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO outlook_tasks(
                    keyword, source_ids, source_names, pages, page_size_step,
                    ai_expand, ai_clean, total_count, status, create_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (keyword, source_ids, source_names, pages, page_size_step,
                1 if ai_expand else 0, 1 if ai_clean else 0, 0, 'running', create_at)
            )
            return cursor.lastrowid

    @staticmethod
    def update_task(task_id, total_count, status='completed', error_msg=None):
        """
        更新任务状态和数据量
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE outlook_tasks SET total_count=?, status=?, error_msg=? WHERE id=?",
                (total_count, status, error_msg, task_id)
            )

    @staticmethod
    def get_task_list(page=1, page_size=20, keyword=None):
        """
        获取任务列表（支持分页和关键词搜索）
        """
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                count_row = conn.execute(
                    "SELECT COUNT(*) as total FROM outlook_tasks WHERE keyword LIKE ?",
                    (f'%{keyword}%',)
                ).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_tasks WHERE keyword LIKE ? ORDER BY create_at DESC",
                    (f'%{keyword}%',)
                ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) as total FROM outlook_tasks").fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_tasks ORDER BY create_at DESC"
                ).fetchall()
        
        # 添加序号和AI深度采集状态
        data_list = []
        for i, r in enumerate(rows):
            d = dict(r)
            d['_seq'] = total - i
            # 检查是否有深度采集的数据
            deep_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM outlook_data WHERE task_id=? AND ai_deep_status=1",
                (d['id'],)
            ).fetchone()["cnt"]
            d['has_deep_collect'] = 1 if deep_count > 0 else 0
            data_list.append(d)
        
        # 分页切片
        start = offset
        end = offset + page_size
        paged_data = data_list[start:end]
        
        return {
            'total': total,
            'data': paged_data,
            'page': page,
            'page_size': page_size
        }

    @staticmethod
    def get_task(task_id):
        """
        根据ID获取单个任务
        """
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM outlook_tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def delete_task(task_id):
        """
        删除任务及其关联的所有数据
        """
        with get_connection() as conn:
            conn.execute("DELETE FROM outlook_data WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM outlook_tasks WHERE id=?", (task_id,))

    @staticmethod
    def get_task_count():
        """
        获取任务总数
        """
        with get_connection() as conn:
            count_row = conn.execute("SELECT COUNT(*) as total FROM outlook_tasks").fetchone()
            return count_row["total"]

    @staticmethod
    def get_total_data_count():
        """
        获取所有任务的数据总量
        """
        with get_connection() as conn:
            count_row = conn.execute("SELECT SUM(total_count) as total FROM outlook_tasks").fetchone()
            return count_row["total"] or 0


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
    def save_data(source_id, source_name, title, url='', content='', author='', publish_date='', raw_html='', ai_processed=0, task_id=0, source_keyword=''):
        try:
            import datetime
            create_at = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO outlook_data(source_id,source_name,title,url,content,author,publish_date,raw_html,ai_processed,task_id,source_keyword,create_at) 
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (source_id, source_name, title, url, content, author, publish_date, raw_html, ai_processed, task_id, source_keyword, create_at)
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

    @staticmethod
    def get_data(data_id):
        """根据ID获取单条数据"""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM outlook_data WHERE id=?", (data_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_ai_deep_status(data_id, status):
        """更新AI深度采集状态"""
        with get_connection() as conn:
            conn.execute("UPDATE outlook_data SET ai_deep_status=? WHERE id=?", (status, data_id))

    @staticmethod
    def get_data_by_task_id(task_id):
        """根据任务ID获取所有数据"""
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM outlook_data WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
            return [dict(r) for r in rows]


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

        # Save source_keyword before cleaning (AI won't return it)
        keyword_map = {}
        for idx, item in enumerate(raw_items):
            if isinstance(item, dict):
                keyword_map[idx] = item.get('source_keyword', '')

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
                    # Restore source_keyword from original items
                    for idx, c_item in enumerate(cleaned):
                        if idx in keyword_map and keyword_map[idx]:
                            c_item['source_keyword'] = keyword_map[idx]
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
                    date_text = date_nodes[0].text_content().strip()
                    # Validate date format before saving
                    if OutlookCollector._is_valid_date(date_text):
                        item['publish_date'] = date_text
                    else:
                        # Try to find date in other sibling/child elements
                        date_text = OutlookCollector._extract_date_from_node(node)
                        if date_text:
                            item['publish_date'] = date_text

            if author_selector:
                author_nodes = node.xpath(author_selector)
                if author_nodes:
                    an = author_nodes[0]
                    if hasattr(an, 'text_content'):
                        item['author'] = an.text_content().strip()
                    elif hasattr(an, 'text') and an.text:
                        item['author'] = an.text.strip()

            if item.get('title'):
                items.append(item)

        return items

    @staticmethod
    def _is_valid_date(text):
        """Check if text looks like a valid date string"""
        import re
        if not text:
            return False
        # Common date patterns
        date_patterns = [
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}',  # 2024-01-01 or 2024年1月1日
            r'\d{1,2}[-/月]\d{1,2}',  # 01-01 or 1月1日
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # 2024/01/01
            r'\d{1,2}:\d{2}',  # Time only (fallback)
            r'今天|昨天|前天|刚刚|\d+分钟前|\d+小时前|\d+天前',  # Relative dates
        ]
        return any(re.search(p, text) for p in date_patterns)

    @staticmethod
    def _extract_date_from_node(node):
        """Try to extract date from node's siblings or children"""
        import re
        # Check all text content in the node for date patterns
        all_text = node.text_content()
        date_patterns = [
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?',
            r'\d{1,2}月\d{1,2}日',
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            r'今天|昨天|前天',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, all_text)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def collect(source, keyword, pages=1, page_size_step=10, use_ai_expand=False, use_ai_clean=False, task_id=0):
        return OutlookCollector.collect_with_status(source, keyword, pages, page_size_step, use_ai_expand, use_ai_clean, task_id, status_callback=None)

    @staticmethod
    def collect_with_status(source, keyword, pages=1, page_size_step=10, use_ai_expand=False, use_ai_clean=False, task_id=0, status_callback=None):
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
            if status_callback:
                status_callback({
                    'logs': [{'time': time.strftime('%H:%M:%S'), 'type': 'info', 'msg': f'AI关键词扩展: {keyword} → {len(keywords)}个关键词'}]
                })

        page_start = source.get('page_start', 0)
        page_fetch_times = []
        page_parse_counts = []

        # Step 2: Fetch and parse pages
        session = OutlookCollector.create_session(source.get('request_headers', ''))

        total_urls = pages
        for page_num in range(pages):
            kw = keywords[page_num % len(keywords)]
            url = OutlookCollector.build_url(
                source['entry_url'], kw, page_num, page_size_step, page_start
            )
            print(f"[Collect] Step 2.{page_num+1}/{pages}: keyword='{kw}', page={page_num+1}/{pages}")
            print(f"[Collect]   URL: {url}")

            if status_callback:
                status_callback({
                    'current_url': page_num + 1,
                    'total_urls': pages,
                    'logs': [{'time': time.strftime('%H:%M:%S'), 'type': 'info', 'msg': f'正在采集第{page_num+1}页...'}]
                })

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
                if status_callback:
                    status_callback({
                        'fail_count': 1,
                        'logs': [{'time': time.strftime('%H:%M:%S'), 'type': 'warn', 'msg': f'第{page_num+1}页获取失败 (HTTP {status_code})'}]
                    })
                continue

            # Check captcha
            if '验证码' in html_content or 'captcha' in html_content.lower():
                print(f"[Collect]   SKIP: Captcha detected")
                page_parse_counts.append(0)
                if status_callback:
                    status_callback({
                        'fail_count': 1,
                        'logs': [{'time': time.strftime('%H:%M:%S'), 'type': 'warn', 'msg': f'第{page_num+1}页检测到验证码'}]
                    })
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
                t = item.get('title', '')[:60].encode('gbk', errors='ignore').decode('gbk')
                d = item.get('publish_date', '').encode('gbk', errors='ignore').decode('gbk')
                print(f"[Collect]     Item {idx+1}: title='{t}', date='{d}'")
            if len(items) > 2:
                print(f"[Collect]     ... and {len(items) - 2} more items")

            if status_callback:
                status_callback({
                    'success_count': len(items),
                    'total_count': len(items),
                    'logs': [{'time': time.strftime('%H:%M:%S'), 'type': 'success', 'msg': f'完成第{page_num+1}页采集 ({len(items)}条)'}]
                })

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
                # Ensure source_keyword is never empty - fallback to search keyword
                skw = item.get('source_keyword', '')
                if not skw:
                    skw = keyword
                saved = OutlookDataRepository.save_data(
                    source_id=source['id'],
                    source_name=source['name'],
                    title=item.get('title', ''),
                    url=item.get('url', ''),
                    content=item.get('content', ''),
                    author=item.get('author', ''),
                    publish_date=item.get('publish_date', ''),
                    raw_html='',
                    ai_processed=ai_processed,
                    task_id=task_id,
                    source_keyword=skw
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


# AI深度采集进度和日志存储（内存中，服务重启后清空）
_deep_collect_progress = {}


class OutlookDeepCollectRepository:
    """AI深度采集"""

    @staticmethod
    def get_progress(task_id):
        return _deep_collect_progress.get(task_id, None)

    @staticmethod
    def set_progress(task_id, progress):
        _deep_collect_progress[task_id] = progress

    @staticmethod
    def clear_progress(task_id):
        _deep_collect_progress.pop(task_id, None)

    @staticmethod
    def deep_collect(data_ids, callback=None):
        """
        AI深度采集
        :param data_ids: 数据ID列表
        :param callback: 进度回调函数 callback(current, total, log_msg, data_id, status)
        :return: 统计结果
        """
        model_config = ModelRepository.get_default_model()
        if not model_config:
            return {"success": 0, "failed": 0, "error": "未找到可用的默认模型"}

        total = len(data_ids)
        success_count = 0
        failed_count = 0
        results = []

        for idx, data_id in enumerate(data_ids):
            current = idx + 1
            data_row = OutlookDataRepository.get_data(data_id)
            if not data_row:
                failed_count += 1
                log_msg = f"[{current}/{total}] 数据ID {data_id} 不存在"
                if callback:
                    callback(current, total, log_msg, data_id, "failed")
                continue

            url = data_row.get('url', '')
            title = data_row.get('title', '')
            content = data_row.get('content', '')

            if not url:
                failed_count += 1
                log_msg = f"[{current}/{total}] {title} - 无URL，跳过深度采集"
                if callback:
                    callback(current, total, log_msg, data_id, "failed")
                continue

            log_msg = f"[{current}/{total}] 开始深度采集: {title}"
            if callback:
                callback(current, total, log_msg, data_id, "processing")

            try:
                # Step 1: 使用Crawl4AI抓取页面（模拟浏览器，绕过反爬）
                log_msg = f"[{current}/{total}] 正在抓取页面: {url}"
                if callback:
                    callback(current, total, log_msg, data_id, "processing")

                markdown_content, raw_html = OutlookDeepCollectRepository._fetch_page_with_crawl4ai(url)

                if not markdown_content and not raw_html:
                    failed_count += 1
                    log_msg = f"[{current}/{total}] {title} - 页面内容为空"
                    if callback:
                        callback(current, total, log_msg, data_id, "failed")
                    OutlookDeepCollectRepository._save_detail(
                        data_id=data_id, task_id=data_row.get('task_id', 0),
                        source_id=data_row.get('source_id', 0), source_name=data_row.get('source_name', ''),
                        title=title, url=url, raw_content='', deep_content='',
                        summary='', key_points='', model_used=model_config.get('name', ''),
                        status='failed', error_msg='页面内容为空'
                    )
                    continue

                log_msg = f"[{current}/{total}] 页面抓取成功，原始内容长度: {len(raw_html)} 字符"
                if callback:
                    callback(current, total, log_msg, data_id, "processing")

                # Step 2: 使用大模型深度解析（先给原始内容，让AI清洗提取）
                log_msg = f"[{current}/{total}] 正在AI深度解析..."
                if callback:
                    callback(current, total, log_msg, data_id, "processing")

                ai_result = OutlookDeepCollectRepository._ai_deep_parse(raw_html, markdown_content, title, model_config)

                # 检查AI是否提取到有效内容
                content = ai_result.get('content', '').strip()
                summary = ai_result.get('summary', '').strip()
                if not content and not summary:
                    failed_count += 1
                    log_msg = f"[{current}/{total}] {title} - 采集失败: 未能提取有效内容"
                    if callback:
                        callback(current, total, log_msg, data_id, "failed")
                    OutlookDeepCollectRepository._save_detail(
                        data_id=data_id, task_id=data_row.get('task_id', 0),
                        source_id=data_row.get('source_id', 0), source_name=data_row.get('source_name', ''),
                        title=title, url=url, raw_content=raw_html[:50000] if raw_html else '',
                        deep_content='', summary='', key_points='',
                        model_used=model_config.get('name', ''),
                        status='failed', error_msg='未能提取有效内容'
                    )
                    continue

                # Step 3: 保存结果（原始内容+清洗后内容）
                detail_id = OutlookDeepCollectRepository._save_detail(
                    data_id=data_id,
                    task_id=data_row.get('task_id', 0),
                    source_id=data_row.get('source_id', 0),
                    source_name=data_row.get('source_name', ''),
                    title=title,
                    url=url,
                    raw_content=raw_html[:50000] if raw_html else '',
                    deep_content=content,
                    summary=summary,
                    key_points=ai_result.get('key_points', ''),
                    model_used=model_config.get('name', ''),
                    status='success'
                )

                # 更新原数据的深度采集状态
                OutlookDataRepository.update_ai_deep_status(data_id, 1)

                success_count += 1
                log_msg = f"[{current}/{total}] {title} - 深度采集完成"
                if callback:
                    callback(current, total, log_msg, data_id, "success")

            except Exception as e:
                failed_count += 1
                log_msg = f"[{current}/{total}] {title} - 采集失败: {str(e)}"
                if callback:
                    callback(current, total, log_msg, data_id, "failed")

                # 保存失败记录
                OutlookDeepCollectRepository._save_detail(
                    data_id=data_id,
                    task_id=data_row.get('task_id', 0),
                    source_id=data_row.get('source_id', 0),
                    source_name=data_row.get('source_name', ''),
                    title=title,
                    url=url,
                    raw_content='',
                    deep_content='',
                    summary='',
                    key_points='',
                    model_used=model_config.get('name', ''),
                    status='failed',
                    error_msg=str(e)
                )

        return {"success": success_count, "failed": failed_count, "total": total}

    @staticmethod
    def _fetch_page_with_crawl4ai(url):
        """
        抓取页面内容，优先使用Playwright真实浏览器（绕过WAF/反爬/JS渲染），
        httpx仅作兜底
        返回 (markdown文本, 原始HTML文本)
        """
        # 优先使用Playwright真实浏览器
        if HAS_PLAYWRIGHT:
            try:
                print(f"[DeepCollect] Playwright抓取: {url[:80]}")
                html = OutlookDeepCollectRepository._fetch_with_playwright(url)
                if html:
                    text = OutlookDeepCollectRepository._extract_text_from_html(html)
                    if len(text.strip()) > 100:
                        print(f"[DeepCollect] Playwright成功，内容长度: {len(html)}")
                        return text, html
                    else:
                        print(f"[DeepCollect] Playwright内容过短({len(text.strip())}字符)，尝试httpx")
            except Exception as e:
                print(f"[DeepCollect] Playwright失败: {e}，降级到httpx")

        # Playwright不可用或失败时，用httpx兜底
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        ]

        simple_headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        }

        last_error = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(1, 3))
                    simple_headers["User-Agent"] = random.choice(user_agents)

                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    resp = client.get(url, headers=simple_headers)
                    if resp.status_code in (403, 412, 502, 503, 504):
                        last_error = f"页面返回HTTP {resp.status_code}"
                        continue
                    resp.raise_for_status()
                    raw_html = resp.text
                    markdown_text = OutlookDeepCollectRepository._extract_text_from_html(raw_html)
                    return markdown_text, raw_html
            except httpx.HTTPStatusError as e:
                last_error = f"页面返回HTTP {e.response.status_code}"
                continue
            except httpx.RequestError as e:
                last_error = f"网络请求错误: {str(e)}"
                continue

        raise Exception(last_error or "页面抓取失败")

    @staticmethod
    def _fetch_with_playwright(url):
        """使用Playwright渲染JS页面，返回完整HTML"""
        async def _render():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until='networkidle', timeout=30000)
                html = await page.content()
                await browser.close()
                return html
        return asyncio.run(_render())

    @staticmethod
    def _extract_text_from_html(html):
        """从HTML中提取正文文本，去除script/style等"""
        # 去除script、style、nav、footer、header等
        html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<aside[^>]*>[\s\S]*?</aside>', '', html, flags=re.IGNORECASE)
        # 去除注释
        html = re.sub(r'<!--[\s\S]*?-->', '', html)
        # 去除HTML标签
        text = re.sub(r'<[^>]+>', ' ', html)
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _ai_deep_parse(raw_html, markdown_content, title, model_config):
        """
        使用大模型深度解析页面内容
        先给原始HTML让AI理解结构，再给markdown作为参考
        """
        # 截取内容，避免token过多
        max_html_len = 15000
        max_md_len = 8000
        if len(raw_html) > max_html_len:
            raw_html = raw_html[:max_html_len] + "...[HTML内容已截断]"
        if len(markdown_content) > max_md_len:
            markdown_content = markdown_content[:max_md_len] + "...[Markdown内容已截断]"

        prompt = f"""你是一个专业的网页内容提取专家。请分析以下网页内容，提取出有价值的正文信息。

标题：{title}

【原始HTML片段】（用于理解页面结构）：
{raw_html}

【页面文本内容】（已清理的正文）：
{markdown_content}

请完成以下任务：
1. 提取完整的正文内容，去除导航、广告、侧边栏、页脚等无关内容
2. 用200字以内概括文章核心内容
3. 提取3-5个关键要点

请严格按以下JSON格式输出（不要输出其他内容）：
{{
  "summary": "文章核心内容概括（200字以内）",
  "key_points": "关键要点1；关键要点2；关键要点3",
  "content": "完整的正文内容，保留原有的段落结构、标题、列表等格式"
}}"""

        messages = [{"role": "user", "content": prompt}]
        response_text = ModelRepository.call_model_api(
            model_config['api_url'],
            model_config['api_key'],
            model_config.get('code', 'default'),
            messages,
            temperature=0.3,
            max_tokens=8000
        )

        # 解析JSON结果
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'summary': result.get('summary', ''),
                    'key_points': result.get('key_points', ''),
                    'content': result.get('content', markdown_content)
                }
        except (json.JSONDecodeError, Exception):
            pass

        # 如果解析失败，返回markdown内容
        return {
            'summary': '',
            'key_points': '',
            'content': markdown_content
        }

    @staticmethod
    def _save_detail(data_id, task_id, source_id, source_name, title, url,
                    raw_content, deep_content, summary, key_points, model_used, status, error_msg=None):
        """保存深度采集结果"""
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO outlook_data_detail(
                    data_id, task_id, source_id, source_name, title, url,
                    raw_content, deep_content, summary, key_points, model_used, status, error_msg
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data_id, task_id, source_id, source_name, title, url,
                raw_content, deep_content, summary, key_points, model_used, status, error_msg)
            )
            return cursor.lastrowid

    @staticmethod
    def get_detail_by_data_id(data_id):
        """根据数据ID获取深度采集结果"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM outlook_data_detail WHERE data_id=? ORDER BY id DESC LIMIT 1",
                (data_id,)
            ).fetchone()
            return dict(row) if row else None
