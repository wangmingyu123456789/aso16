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
                "SELECT * FROM outlook_sources ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_active_sources():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM outlook_sources WHERE status=1 ORDER BY id ASC"
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
        create_at = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
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
        删除任务及其关联的所有数据（含深度采集详情）
        """
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM outlook_data_detail WHERE data_id IN (SELECT id FROM outlook_data WHERE task_id=?)",
                (task_id,)
            )
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
        except Exception as e:
            print(f"[save_data] FAILED: source_id={source_id} title={title[:50] if title else ''} error={e}", flush=True)
            return False

    @staticmethod
    def delete_data(data_id):
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM outlook_data_detail WHERE data_id=?", (data_id,))
                conn.execute("DELETE FROM outlook_data WHERE id=?", (data_id,))
                return True
        except Exception:
            return False

    @staticmethod
    def delete_data_batch(data_ids):
        try:
            with get_connection() as conn:
                detail_placeholders = ','.join(['?'] * len(data_ids))
                conn.execute(
                    f"DELETE FROM outlook_data_detail WHERE data_id IN ({detail_placeholders})",
                    data_ids
                )
                conn.execute(
                    f"DELETE FROM outlook_data WHERE id IN ({detail_placeholders})",
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
    def parse_html(html_content, html_selector, title_selector, url_selector, content_selector, date_selector, author_selector, entry_url=''):
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

        source_domain = OutlookCollector._resolve_source_domain(entry_url)

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

            raw_url = item.get('url', '')
            if raw_url:
                item['url'] = OutlookCollector._resolve_url_to_absolute(raw_url, source_domain, entry_url)

            if content_selector:
                content_nodes = node.xpath(content_selector)
                if content_nodes:
                    item['content'] = content_nodes[0].text_content().strip()
            if not item.get('content'):
                node_text = node.text_content().strip()
                node_text = re.sub(r'\s+', ' ', node_text)
                item['content'] = node_text[:2000]
            raw_node_html = lxml_html.tostring(node, encoding='unicode', pretty_print=True)[:5000]
            item['raw_html_snippet'] = raw_node_html

            node_full_text = node.text_content()

            if date_selector:
                date_nodes = node.xpath(date_selector)
                if date_nodes:
                    date_text = date_nodes[0].text_content().strip()
                    if OutlookCollector._is_valid_date(date_text):
                        item['publish_date'] = date_text
                    else:
                        date_text = OutlookCollector._extract_date_from_node(node)
                        if date_text:
                            item['publish_date'] = date_text

            if not item.get('publish_date'):
                extracted_date = OutlookCollector._extract_date_from_text(node_full_text)
                if extracted_date:
                    item['publish_date'] = extracted_date

            if author_selector:
                author_nodes = node.xpath(author_selector)
                if author_nodes:
                    an = author_nodes[0]
                    if hasattr(an, 'text_content'):
                        item['author'] = an.text_content().strip()
                    elif hasattr(an, 'text') and an.text:
                        item['author'] = an.text.strip()

            if not item.get('author'):
                extracted_author = OutlookCollector._extract_author_from_text(node_full_text)
                if extracted_author:
                    item['author'] = extracted_author

            if item.get('title'):
                items.append(item)

        return items

    @staticmethod
    def _resolve_source_domain(entry_url):
        from urllib.parse import urlparse
        parsed = urlparse(entry_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _resolve_url_to_absolute(raw_url, source_domain, entry_url):
        if raw_url.startswith('http://') or raw_url.startswith('https://'):
            return raw_url
        if raw_url.startswith('//'):
            return 'https:' + raw_url
        if raw_url.startswith('/'):
            return source_domain + raw_url
        from urllib.parse import urljoin
        return urljoin(entry_url, raw_url)

    @staticmethod
    def _extract_author_from_text(text):
        import re
        if not text:
            return ''
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.search(r'[\u4e00-\u9fff]{2,10}$', line) and len(line) < 30:
                candidates = re.findall(r'[\u4e00-\u9fff\u00b7]{2,15}', line)
                keyword_found = False
                for i, c in enumerate(candidates):
                    if any(kw in c for kw in ['来源', '作者', '责任编辑', '编辑']):
                        keyword_found = True
                        if i + 1 < len(candidates):
                            return candidates[i + 1]
                if not keyword_found:
                    for c in candidates:
                        if len(line) < 20 and any(kw in line for kw in ['网', '新闻', '报', '社']):
                            return line
        relative_date_match = re.search(r'\d+分钟前|\d+小时前|\d+天前|今天|昨天|刚刚', text)
        if relative_date_match:
            before = text[:relative_date_match.start()].strip()
            candidates = re.findall(r'[\u4e00-\u9fff]{2,10}', before)
            for c in reversed(candidates):
                if len(c) >= 2:
                    return c
        if re.search(r'\d{4}年', text):
            before = re.split(r'\d{4}年', text)[0].strip()
            if before:
                candidates = re.findall(r'[\u4e00-\u9fff]{2,10}', before)
                for c in reversed(candidates):
                    if len(c) >= 2 and not any(kw in c for kw in ['摘要', '标题', '关键词']):
                        return c
        return ''

    @staticmethod
    def _extract_date_from_text(text):
        import re
        if not text:
            return ''
        patterns = [
            r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日]?',
            r'(\d{1,2})月(\d{1,2})日',
        ]
        best = ''
        for p in patterns:
            m = re.search(p, text)
            if m:
                candidate = m.group(0)
                if len(candidate) > len(best):
                    best = candidate
        relative = re.search(r'今天|昨天|前天|刚刚|\d+分钟前|\d+小时前|\d+天前', text)
        if relative and not best:
            best = relative.group(0)
        return best

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
                source.get('author_selector', ''),
                source.get('entry_url', '')
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
                    raw_html=item.get('raw_html_snippet', ''),
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
        model_config = ModelRepository.get_default_model()
        if not model_config:
            return {"success": 0, "failed": 0, "error": "未找到可用的默认模型"}

        total = len(data_ids)
        success_count = 0
        failed_count = 0

        for idx, data_id in enumerate(data_ids):
            current = idx + 1
            data_row = OutlookDataRepository.get_data(data_id)
            if not data_row:
                failed_count += 1
                if callback:
                    callback(current, total, f"[{current}/{total}] 数据ID {data_id} 不存在", data_id, "failed")
                continue

            url = (data_row.get('url') or '').strip()
            title = (data_row.get('title') or '').strip()
            source_name = data_row.get('source_name', '')
            source_id = data_row.get('source_id', 0)
            task_id = data_row.get('task_id', 0)
            snippet = (data_row.get('content') or '').strip()
            raw_html_snippet = (data_row.get('raw_html') or '').strip()

            if callback:
                callback(current, total, f"[{current}/{total}] 开始深度采集: {title}", data_id, "processing")

            try:
                resolved_url = OutlookDeepCollectRepository._resolve_url(url, source_name)
                is_redirect = OutlookDeepCollectRepository._is_redirect_url(resolved_url)

                if is_redirect:
                    if callback:
                        callback(current, total, f"[{current}/{total}] 检测到跳转链接，尝试通过标题搜索获取内容: {title[:40]}", data_id, "processing")
                    content_text, raw_html_content = OutlookDeepCollectRepository._fetch_by_title_search(
                        title, source_name, snippet, raw_html_snippet
                    )
                    fetch_note = "通过标题搜索获取"
                else:
                    if callback:
                        callback(current, total, f"[{current}/{total}] 正在抓取页面: {resolved_url}", data_id, "processing")
                    content_text, raw_html_content, fetch_note = OutlookDeepCollectRepository._fetch_page_robust(resolved_url, title)

                if callback:
                    callback(current, total, f"[{current}/{total}] 内容准备完成 ({fetch_note})", data_id, "processing")

                if callback:
                    callback(current, total, f"[{current}/{total}] 正在AI深度解析...", data_id, "processing")

                ai_result = OutlookDeepCollectRepository._ai_deep_parse(
                    raw_html_content or raw_html_snippet, content_text, title, snippet, model_config
                )

                deep_content = ai_result.get('content', '').strip() or content_text
                summary = ai_result.get('summary', '').strip()
                key_points = ai_result.get('key_points', '').strip()

                has_valid_content = bool(summary) or (
                    len(deep_content) > 30 and not OutlookDeepCollectRepository._is_binary_content(deep_content)
                )
                status = 'success' if has_valid_content else 'success_with_limited'

                OutlookDeepCollectRepository._save_detail(
                    data_id=data_id, task_id=task_id,
                    source_id=source_id, source_name=source_name,
                    title=title, url=resolved_url,
                    raw_content=(raw_html_content or raw_html_snippet or '')[:20000],
                    deep_content=deep_content,
                    summary=summary, key_points=key_points,
                    model_used=model_config.get('name', ''),
                    status=status
                )

                OutlookDataRepository.update_ai_deep_status(data_id, 1)
                success_count += 1
                if callback:
                    callback(current, total, f"[{current}/{total}] {title[:30]} - 深度采集完成", data_id, "success")

            except Exception as e:
                failed_count += 1
                if callback:
                    callback(current, total, f"[{current}/{total}] {title[:30]} - 采集失败: {str(e)[:60]}", data_id, "failed")
                OutlookDeepCollectRepository._save_detail(
                    data_id=data_id, task_id=task_id,
                    source_id=source_id, source_name=source_name,
                    title=title, url=url,
                    raw_content='', deep_content=snippet or title, summary=title, key_points='',
                    model_used=model_config.get('name', ''),
                    status='failed', error_msg=str(e)
                )

        return {"success": success_count, "failed": failed_count, "total": total}

    @staticmethod
    def _resolve_url(url, source_name=''):
        if url.startswith('http://') or url.startswith('https://'):
            return url
        if url.startswith('/'):
            domains = {
                'sogou': 'https://www.sogou.com',
                'so_news': 'https://www.so.com',
                '360': 'https://www.so.com',
            }
            for key, domain in domains.items():
                if key in source_name.lower() or key in source_name:
                    return domain + url
            return 'https://www.sogou.com' + url
        return url

    @staticmethod
    def _is_redirect_url(url):
        redirect_patterns = [
            'sogou.com/link', 'so.com/link', 'www.baidu.com/link',
            '/link?url=', '/link?m=',
        ]
        url_lower = url.lower()
        for p in redirect_patterns:
            if p in url_lower:
                return True
        return False

    @staticmethod
    def _is_binary_content(text):
        if not text or len(text) < 20:
            return False
        non_printable = 0
        for ch in text[:500]:
            if ord(ch) < 32 and ord(ch) not in (9, 10, 13):
                non_printable += 1
            elif 127 < ord(ch) < 256:
                non_printable += 1
        ratio = non_printable / min(len(text), 500)
        return ratio > 0.3

    @staticmethod
    def _fetch_by_title_search(title, source_name, snippet, raw_html_snippet):
        """对跳转链接，用标题在搜索引擎重新搜索，拿到真实内容"""
        search_urls = []
        if '搜狗' in source_name or 'sogou' in source_name:
            search_urls.append(f"https://news.sogou.com/news?query={quote(title)}&page=1")
        if '360' in source_name or 'so_news' in source_name:
            search_urls.append(f"https://www.so.com/s?q={quote(title)}&pn=1")

        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        for search_url in search_urls:
            try:
                with httpx.Client(timeout=15.0, follow_redirects=True, verify=False) as client:
                    resp = client.get(search_url, headers=headers)
                    if resp.status_code != 200:
                        continue
                    try:
                        import chardet
                        detected = chardet.detect(resp.content)
                        if detected and detected.get('encoding'):
                            resp.encoding = detected['encoding']
                    except ImportError:
                        resp.encoding = 'utf-8'
                    html = resp.text
                    if len(html) < 1000 or OutlookDeepCollectRepository._is_binary_content(html):
                        continue
                    doc = lxml_html.fromstring(html)
                    if 'sogou' in search_url:
                        items = doc.xpath("//div[contains(@class,'vrwrap')]")
                    else:
                        items = doc.xpath("//li[contains(@class,'res-list')]")
                    for item in items:
                        item_text = item.text_content().strip()
                        item_text_clean = re.sub(r'\s+', ' ', item_text)
                        if title[:20] in item_text_clean:
                            links = item.xpath(".//a")
                            for a in links:
                                href = a.get('href', '')
                                if href and not OutlookDeepCollectRepository._is_redirect_url(href):
                                    try:
                                        with httpx.Client(timeout=15.0, follow_redirects=True, verify=False) as c2:
                                            r2 = c2.get(href, headers=headers)
                                            if r2.status_code == 200:
                                                try:
                                                    detected = chardet.detect(r2.content)
                                                    if detected and detected.get('encoding'):
                                                        r2.encoding = detected['encoding']
                                                except ImportError:
                                                    r2.encoding = 'utf-8'
                                                html2 = r2.text
                                                if not OutlookDeepCollectRepository._is_binary_content(html2) and len(html2) > 1000:
                                                    text2 = OutlookDeepCollectRepository._extract_text_from_html(html2)
                                                    if len(text2.strip()) > 200:
                                                        return text2, html2
                                    except Exception:
                                        pass
            except Exception:
                pass

        if snippet:
            return f"标题：{title}\n来源：{source_name}\n摘要：{snippet}", raw_html_snippet
        return f"标题：{title}\n来源：{source_name}", raw_html_snippet

    @staticmethod
    def _fetch_page_robust(url, article_title=''):
        def _try_httpx(fetch_url, extra_headers=None):
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            if extra_headers:
                headers.update(extra_headers)
            try:
                with httpx.Client(timeout=15.0, follow_redirects=True, verify=False) as client:
                    resp = client.get(fetch_url, headers=headers)
                    if resp.status_code == 200:
                        try:
                            import chardet
                            detected = chardet.detect(resp.content)
                            if detected and detected.get('encoding'):
                                resp.encoding = detected['encoding']
                        except ImportError:
                            resp.encoding = 'utf-8'
                        raw_html = resp.text
                        if OutlookDeepCollectRepository._is_binary_content(raw_html):
                            return None, None, None
                        clean_text = OutlookDeepCollectRepository._extract_text_from_html(raw_html)
                        return clean_text, raw_html, resp.url
            except Exception:
                pass
            return None, None, None

        if HAS_PLAYWRIGHT:
            try:
                html = OutlookDeepCollectRepository._fetch_with_playwright(url)
                if html:
                    text = OutlookDeepCollectRepository._extract_text_from_html(html)
                    if not OutlookDeepCollectRepository._is_binary_content(text) and len(text.strip()) > 200:
                        return text, html, "Playwright"
            except Exception:
                pass

        clean_text, raw_html, final_url = _try_httpx(url)
        if clean_text and len(clean_text.strip()) > 200 and not OutlookDeepCollectRepository._is_binary_content(clean_text):
            return clean_text, raw_html, "httpx"

        clean_text, raw_html, final_url = _try_httpx(url, {
            "Referer": "https://www.baidu.com/",
            "User-Agent": "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
        })
        if clean_text and len(clean_text.strip()) > 200 and not OutlookDeepCollectRepository._is_binary_content(clean_text):
            return clean_text, raw_html, "httpx(Baiduspider)"

        return article_title, '', "无法获取页面正文"

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
    def _extract_text_from_html(html_content):
        if not html_content:
            return ''
        try:
            doc = lxml_html.fromstring(html_content)
            for tag in ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe', 'form', 'svg']:
                for el in doc.xpath(f'//{tag}'):
                    el.getparent().remove(el)
            for el in doc.xpath('//comment()'):
                el.getparent().remove(el)
            content_candidates = []
            for sel in ['//article', '//main', '//div[@class="article"]', '//div[@class="content"]',
                        '//div[contains(@class,"article-content")]', '//div[contains(@class,"post-content")]',
                        '//div[contains(@class,"entry-content")]', '//div[contains(@class,"news-content")]',
                        '//div[contains(@class,"main-content")]', '//div[contains(@class,"text-content")]',
                        '//div[@id="content"]', '//div[@id="article"]', '//div[@id="main"]',
                        '//div[contains(@class,"detail")]', '//div[contains(@class,"news-detail")]']:
                nodes = doc.xpath(sel)
                for n in nodes:
                    text = n.text_content().strip()
                    if len(text) > 200:
                        content_candidates.append((len(text), n))
            if content_candidates:
                content_candidates.sort(key=lambda x: x[0], reverse=True)
                _, best = content_candidates[0]
                raw = OutlookDeepCollectRepository._element_to_text(best)
                if len(raw) > 100:
                    return raw
            body = doc.xpath('//body')
            if body:
                raw = OutlookDeepCollectRepository._element_to_text(body[0])
                if len(raw) > 50:
                    return raw
        except Exception:
            pass
        html_clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html_content, flags=re.IGNORECASE)
        html_clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html_clean, flags=re.IGNORECASE)
        html_clean = re.sub(r'<!--[\s\S]*?-->', '', html_clean)
        html_clean = re.sub(r'<br\s*/?>', '\n', html_clean)
        html_clean = re.sub(r'</p>', '\n', html_clean)
        html_clean = re.sub(r'</div>', '\n', html_clean)
        html_clean = re.sub(r'</h[1-6]>', '\n', html_clean)
        html_clean = re.sub(r'</li>', '\n', html_clean)
        html_clean = re.sub(r'<[^>]+>', ' ', html_clean)
        lines = html_clean.split('\n')
        cleaned = []
        for line in lines:
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                cleaned.append(line)
        return '\n'.join(cleaned)

    @staticmethod
    def _element_to_text(el):
        lines = []
        for child in el.iter():
            tag = child.tag if hasattr(child, 'tag') else ''
            text = child.text_content().strip() if hasattr(child, 'text_content') else ''
            if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                if text:
                    lines.append(text)
            elif tag == 'br':
                if lines:
                    lines.append('')
            elif tag == 'li':
                if text:
                    lines.append(f'- {text}')
            elif tag in ('div', 'section', 'article', 'main'):
                pass
        return '\n'.join(lines) if lines else el.text_content().strip()

    @staticmethod
    def _ai_deep_parse(raw_html, clean_text, title, snippet='', model_config=None):
        if not model_config:
            return {'summary': '', 'key_points': '', 'content': clean_text}

        if len(clean_text) > 18000:
            clean_text = clean_text[:18000]

        context_parts = [f"## 文章标题\n{title}"]
        if snippet:
            context_parts.append(f"## 搜索摘要\n{snippet}")
        context_parts.append(f"## 页面正文\n{clean_text}")
        context_str = '\n\n'.join(context_parts)

        prompt = (
            "你是一个信息整理助手。请根据以下内容，完成提取和整理工作。\n\n"
            f"{context_str}\n\n"
            "请执行：\n"
            "1. 提取正文内容，去除明显的导航、广告、版权声明等无关信息。如果没有明显无关内容，请完整保留原文。\n"
            "2. 用200字以内概括核心内容\n"
            "3. 提取3-5个关键要点\n\n"
            "注意：请尽可能多地保留原文内容，不要过度删减。\n\n"
            '请按以下JSON格式输出：\n'
            '{"summary": "文章核心内容概括（200字以内）", "key_points": "要点1；要点2；要点3", "content": "完整的正文内容"}'
        )

        messages = [{"role": "user", "content": prompt}]
        response_text = ModelRepository.call_model_api(
            model_config['api_url'],
            model_config['api_key'],
            model_config.get('code', 'default'),
            messages,
            temperature=0.3,
            max_tokens=8000
        )

        result = OutlookDeepCollectRepository._parse_ai_json_response(response_text)
        if result:
            return result

        messages.append({"role": "assistant", "content": response_text})
        messages.append({
            "role": "user",
            "content": '格式错误，请严格按JSON输出：{"summary": "...", "key_points": "...", "content": "..."}'
        })
        response_text = ModelRepository.call_model_api(
            model_config['api_url'],
            model_config['api_key'],
            model_config.get('code', 'default'),
            messages,
            temperature=0.2,
            max_tokens=8000
        )
        result = OutlookDeepCollectRepository._parse_ai_json_response(response_text)
        if result:
            return result

        return {'summary': '', 'key_points': '', 'content': clean_text}

    @staticmethod
    def _parse_ai_json_response(response_text):
        if not response_text:
            return None
        code_block = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text)
        if code_block:
            try:
                data = json.loads(code_block.group(1))
                if data.get('summary') or data.get('content'):
                    return {
                        'summary': data.get('summary', ''),
                        'key_points': data.get('key_points', ''),
                        'content': data.get('content', '')
                    }
            except json.JSONDecodeError:
                pass
        brace_match = re.search(r'\{[\s\S]*?\}', response_text)
        if brace_match:
            try:
                data = json.loads(brace_match.group())
                if data.get('summary') or data.get('content'):
                    return {
                        'summary': data.get('summary', ''),
                        'key_points': data.get('key_points', ''),
                        'content': data.get('content', '')
                    }
            except json.JSONDecodeError:
                pass
        return None

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
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM outlook_data_detail WHERE data_id=? ORDER BY id DESC LIMIT 1",
                (data_id,)
            ).fetchone()
            return dict(row) if row else None


class CrawlLogRepository:
	@staticmethod
	def create_log(task_id, source_id, source_name, keyword):
		import datetime
		start_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
		with get_connection() as conn:
			c = conn.execute(
				"INSERT INTO crawl_logs(task_id,source_id,source_name,keyword,start_time,status) VALUES(?,?,?,?,?,?)",
				(task_id, source_id, source_name, keyword, start_time, "running")
			)
		return c.lastrowid

	@staticmethod
	def update_log(log_id, **kwargs):
		updates = []
		params = []
		for k, v in kwargs.items():
			updates.append(f"{k}=?")
			params.append(v)
		if not updates:
			return
		params.append(log_id)
		with get_connection() as conn:
			conn.execute(f"UPDATE crawl_logs SET {','.join(updates)} WHERE id=?", params)

	@staticmethod
	def complete_log(log_id, total_count=0, saved_count=0):
		import datetime
		with get_connection() as conn:
			conn.execute(
				"UPDATE crawl_logs SET end_time=?,total_count=?,saved_count=?,status='completed' WHERE id=?",
				(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), total_count, saved_count, log_id)
			)

	@staticmethod
	def fail_log(log_id, error_msg=""):
		import datetime
		with get_connection() as conn:
			conn.execute(
				"UPDATE crawl_logs SET end_time=?,status='error',error_msg=? WHERE id=?",
				(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), error_msg[:500], log_id)
			)

	@staticmethod
	def get_log_list(page=1, page_size=20):
		offset = (page - 1) * page_size
		with get_connection() as conn:
			total = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs").fetchone()["cnt"]
			rows = conn.execute(
				"SELECT * FROM crawl_logs ORDER BY id DESC LIMIT ? OFFSET ?",
				(page_size, offset)
			).fetchall()
		results = []
		for r in rows:
			d = dict(r)
			d['_seq'] = total - offset - results.__len__()
			results.append(d)
		return {"total": total, "data": results}

	@staticmethod
	def clear_all_logs():
		with get_connection() as conn:
			conn.execute("DELETE FROM crawl_logs")

	@staticmethod
	def get_stats():
		with get_connection() as conn:
			total = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs").fetchone()["cnt"]
			success = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='completed'").fetchone()["cnt"]
			running = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='running'").fetchone()["cnt"]
			error = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='error'").fetchone()["cnt"]
		return {"total": total, "success": success, "running": running, "error": error}


class CrawlScheduleRepository:
	@staticmethod
	def get_all_enabled():
		with get_connection() as conn:
			rows = conn.execute("SELECT * FROM crawl_schedules WHERE is_enabled=1").fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def add_schedule(source_id, source_name, keyword, cron_expression, pages=1, per_page=10, is_enabled=1, sch_year=0):
		try:
			import datetime
			create_at = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
			with get_connection() as conn:
				conn.execute(
					"INSERT INTO crawl_schedules(source_id,source_name,keyword,cron_expression,sch_year,pages,per_page,is_enabled,create_at) VALUES(?,?,?,?,?,?,?,?,?)",
					(source_id, source_name, keyword, cron_expression, sch_year, pages, per_page, is_enabled, create_at)
				)
			print(f"[add_schedule] OK: source_id={source_id}, cron={cron_expression}, sch_year={sch_year}, enabled={is_enabled}", flush=True)
			return True
		except Exception as e:
			import traceback
			print(f"[add_schedule] FAILED: {e}", flush=True)
			traceback.print_exc()
			return False

	@staticmethod
	def update_schedule(schedule_id, **kwargs):
		updates = []
		params = []
		for k, v in kwargs.items():
			updates.append(f"{k}=?")
			params.append(v)
		if not updates:
			return False
		params.append(schedule_id)
		try:
			with get_connection() as conn:
				conn.execute(f"UPDATE crawl_schedules SET {','.join(updates)} WHERE id=?", params)
			return True
		except Exception as e:
			print(f"[update_schedule] FAILED: {e}", flush=True)
			return False

	@staticmethod
	def delete_schedule(schedule_id):
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM crawl_schedules WHERE id=?", (schedule_id,))
			return True
		except Exception:
			return False

	@staticmethod
	def batch_delete(ids):
		try:
			with get_connection() as conn:
				placeholders = ','.join(['?'] * len(ids))
				conn.execute(f"DELETE FROM crawl_schedules WHERE id IN ({placeholders})", ids)
			return True
		except Exception:
			return False

	@staticmethod
	def get_schedule_list(page=1, page_size=20):
		offset = (page - 1) * page_size
		with get_connection() as conn:
			total = conn.execute("SELECT COUNT(*) as cnt FROM crawl_schedules").fetchone()["cnt"]
			rows = conn.execute(
				"""SELECT cs.*, os.name as source_display_name,
				(SELECT status FROM crawl_logs WHERE task_id=cs.id ORDER BY id DESC LIMIT 1) as last_log_status
				FROM crawl_schedules cs
				LEFT JOIN outlook_sources os ON cs.source_id=os.id
				ORDER BY cs.id DESC LIMIT ? OFFSET ?""",
				(page_size, offset)
			).fetchall()
		return {"total": total, "data": [dict(r) for r in rows]}

	@staticmethod
	def get_schedule_by_id(schedule_id):
		with get_connection() as conn:
			row = conn.execute(
				"""SELECT cs.*, os.name as source_display_name,
				(SELECT status FROM crawl_logs WHERE task_id=cs.id ORDER BY id DESC LIMIT 1) as last_log_status
				FROM crawl_schedules cs
				LEFT JOIN outlook_sources os ON cs.source_id=os.id
				WHERE cs.id=?""",
				(schedule_id,)
			).fetchone()
		return dict(row) if row else None
