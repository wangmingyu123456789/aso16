import json
import time
import threading
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.outlook import OutlookSourceRepository, OutlookDataRepository, OutlookTaskRepository, OutlookCollector
from app.models.db import get_connection

# 采集状态存储（内存中）
_collect_status = {}
_status_lock = threading.Lock()

def set_collect_status(task_id, status):
    with _status_lock:
        _collect_status[str(task_id)] = {
            **status,
            'update_time': time.time()
        }

def get_collect_status(task_id):
    with _status_lock:
        return _collect_status.get(str(task_id), {})

def clear_collect_status(task_id):
    with _status_lock:
        _collect_status.pop(str(task_id), None)

class AdminOutlookRedirectHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.redirect("/admin/outlook/sources")

class AdminOutlookSourceListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/outlook_source_list.html", title="瞭望数据源", username=self.current_user, current_page='outlook_source')

class AdminOutlookSourceApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = OutlookSourceRepository.get_all_sources()
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "data": sources
        })

class AdminOutlookSourceAddHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        entry_url = (self.get_body_argument("entry_url", "") or "").strip()
        method = self.get_body_argument("method", "GET")
        headers = (self.get_body_argument("headers", "") or "").strip()
        parser_type = self.get_body_argument("parser_type", "html")
        html_selector = (self.get_body_argument("html_selector", "") or "").strip()
        title_selector = (self.get_body_argument("title_selector", "") or "").strip()
        url_selector = (self.get_body_argument("url_selector", "") or "").strip()
        content_selector = (self.get_body_argument("content_selector", "") or "").strip()
        date_selector = (self.get_body_argument("date_selector", "") or "").strip()
        author_selector = (self.get_body_argument("author_selector", "") or "").strip()
        page_size_step = int(self.get_body_argument("page_size_step", "10"))
        page_start = int(self.get_body_argument("page_start", "0"))
        status = int(self.get_body_argument("status", "1"))
        description = (self.get_body_argument("description", "") or "").strip()

        if not name or not code or not entry_url:
            return self.write({"code": 1, "msg": "名称、编码和入口URL不能为空"})

        if OutlookSourceRepository.create_source(
            name, code, entry_url, method, headers, parser_type,
            html_selector, title_selector, url_selector, content_selector,
            date_selector, author_selector, page_size_step, page_start, status, description
        ):
            return self.write({"code": 0, "msg": "新增成功"})
        return self.write({"code": 1, "msg": "新增失败，编码可能已存在"})

class AdminOutlookSourceEditHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        source_id = int(self.get_body_argument("id", "0"))
        if not source_id:
            return self.write({"code": 1, "msg": "数据源ID不能为空"})

        kwargs = {}
        for field in ['name', 'code', 'entry_url', 'method', 'headers', 'parser_type',
                    'html_selector', 'title_selector', 'url_selector', 'content_selector',
                    'date_selector', 'author_selector', 'description']:
            val = self.get_body_argument(field, None)
            if val is not None:
                kwargs[field] = val.strip()

        page_size_step = self.get_body_argument("page_size_step", None)
        if page_size_step is not None:
            kwargs['page_size_step'] = int(page_size_step)
        page_start = self.get_body_argument("page_start", None)
        if page_start is not None:
            kwargs['page_start'] = int(page_start)
        status = self.get_body_argument("status", None)
        if status is not None:
            kwargs['status'] = int(status)

        if OutlookSourceRepository.update_source(source_id, **kwargs):
            return self.write({"code": 0, "msg": "修改成功"})
        return self.write({"code": 1, "msg": "修改失败"})

class AdminOutlookSourceDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        source_id = int(self.get_body_argument("id", "0"))
        if not source_id:
            return self.write({"code": 1, "msg": "数据源ID不能为空"})
        if OutlookSourceRepository.delete_source(source_id):
            return self.write({"code": 0, "msg": "删除成功"})
        return self.write({"code": 1, "msg": "删除失败"})

class AdminOutlookCollectHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        keyword = (self.get_body_argument("keyword", "") or "").strip()
        source_id_str = self.get_body_argument("source_id", "")
        sources_str = self.get_body_argument("sources", "")
        pages = int(self.get_body_argument("pages", "1"))
        page_size_step = int(self.get_body_argument("page_size_step", "0"))
        ai_expand = self.get_body_argument("ai_expand", "0") == "1"
        ai_clean = self.get_body_argument("ai_clean", "0") == "1"

        if not keyword:
            return self.write({"code": 1, "msg": "请输入采集关键字"})

        source_ids = []
        if source_id_str:
            try:
                source_ids = [int(source_id_str)]
            except Exception:
                return self.write({"code": 1, "msg": "数据源参数格式错误"})
        elif sources_str:
            try:
                source_ids = [int(x) for x in sources_str.split(",") if x.strip()]
            except Exception:
                return self.write({"code": 1, "msg": "数据源参数格式错误"})

        if not source_ids:
            return self.write({"code": 1, "msg": "请至少选择一个数据源"})

        all_sources = OutlookSourceRepository.get_all_sources()
        selected_sources = [s for s in all_sources if s['id'] in source_ids]
        source_ids_str = ",".join(str(s['id']) for s in selected_sources)
        source_names_str = ",".join(s['name'] for s in selected_sources)

        task_id = OutlookTaskRepository.create_task(
            keyword, source_ids_str, source_names_str,
            pages, page_size_step, ai_expand, ai_clean
        )

        # 初始化采集状态
        total_urls = len(selected_sources) * pages
        set_collect_status(task_id, {
            'task_id': task_id,
            'status': 'running',
            'keyword': keyword,
            'total_urls': total_urls,
            'current_url': 0,
            'current_source': '',
            'total_count': 0,
            'success_count': 0,
            'fail_count': 0,
            'start_time': time.time(),
            'logs': [{'time': time.strftime('%H:%M:%S'), 'type': 'info', 'msg': f'开始采集: {keyword}'}]
        })

        total_results = 0
        for source in selected_sources:
            step = page_size_step if page_size_step > 0 else source.get('page_size_step', 10)
            print(f"[Collect] source={source['name']}, keyword={keyword}, pages={pages}, step={step}")

            # 更新当前源
            status = get_collect_status(task_id)
            status['current_source'] = source['name']
            set_collect_status(task_id, status)

            # 创建状态回调闭包，累计计数
            def make_callback(tid):
                def callback(update):
                    current = get_collect_status(tid)
                    # 累计计数
                    if 'success_count' in update:
                        current['success_count'] = current.get('success_count', 0) + update['success_count']
                    if 'fail_count' in update:
                        current['fail_count'] = current.get('fail_count', 0) + update['fail_count']
                    if 'total_count' in update:
                        current['total_count'] = current.get('total_count', 0) + update['total_count']
                    # 更新其他字段
                    for k, v in update.items():
                        if k not in ('success_count', 'fail_count', 'total_count'):
                            current[k] = v
                    set_collect_status(tid, current)
                return callback

            count = OutlookCollector.collect_with_status(
                source, keyword, pages, step,
                use_ai_expand=ai_expand,
                use_ai_clean=ai_clean,
                task_id=task_id,
                status_callback=make_callback(task_id)
            )
            total_results += count
            print(f"[Collect] source={source['name']}, saved={count}")

        # 更新最终状态
        final_status = get_collect_status(task_id)
        final_status['status'] = 'completed'
        final_status['total_count'] = total_results
        final_status['logs'].append({'time': time.strftime('%H:%M:%S'), 'type': 'success', 'msg': f'采集完成，共获取 {total_results} 条数据'})
        set_collect_status(task_id, final_status)

        OutlookTaskRepository.update_task(task_id, total_results)

        return self.write({
            "code": 0,
            "msg": f"采集完成，共获取 {total_results} 条数据",
            "count": total_results,
            "task_id": task_id
        })

class AdminOutlookDataListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/outlook_data_list.html", title="数据仓库", username=self.current_user, current_page='outlook_data')

class AdminOutlookTaskApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "20"))
        keyword = self.get_argument("keyword", "")
        result = OutlookTaskRepository.get_task_list(page=page, page_size=page_size, keyword=keyword if keyword else None)
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["data"]
        })

class AdminOutlookTaskDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        task_id_str = self.get_body_argument("task_id", "")
        if not task_id_str:
            return self.write({"code": 1, "msg": "请选择要删除的任务"})
        try:
            task_id = int(task_id_str)
        except Exception:
            return self.write({"code": 1, "msg": "任务ID格式错误"})
        OutlookTaskRepository.delete_task(task_id)
        return self.write({"code": 0, "msg": "删除成功"})

class AdminOutlookTaskDataHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        task_id = int(self.get_argument("task_id", "0"))
        task = OutlookTaskRepository.get_task(task_id)
        self.render("admin/outlook_task_data.html", title="任务数据", username=self.current_user, current_page='outlook_data', task=task)

class AdminOutlookTaskDataApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        task_id = int(self.get_argument("task_id", "0"))
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "20"))
        keyword = self.get_argument("keyword", "")
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                count_row = conn.execute(
                    "SELECT COUNT(*) as total FROM outlook_data WHERE task_id=? AND title LIKE ?",
                    (task_id, f'%{keyword}%')
                ).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data WHERE task_id=? AND title LIKE ? ORDER BY create_at DESC LIMIT ? OFFSET ?",
                    (task_id, f'%{keyword}%', page_size, offset)
                ).fetchall()
            else:
                count_row = conn.execute(
                    "SELECT COUNT(*) as total FROM outlook_data WHERE task_id=?",
                    (task_id,)
                ).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data WHERE task_id=? ORDER BY create_at DESC LIMIT ? OFFSET ?",
                    (task_id, page_size, offset)
                ).fetchall()
        self.set_header("Content-Type", "application/json")
        data_list = []
        for i, r in enumerate(rows):
            d = dict(r)
            d["_seq"] = total - offset - i
            data_list.append(d)
        self.write({
            "code": 0,
            "msg": "",
            "count": total,
            "data": data_list
        })

class AdminOutlookDataApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "20"))
        keyword = self.get_argument("keyword", "")
        result = OutlookDataRepository.get_data_list(page=page, page_size=page_size, keyword=keyword if keyword else None)
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["data"]
        })

class AdminOutlookDataDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids_str = self.get_body_argument("ids", "")
        if not ids_str:
            return self.write({"code": 1, "msg": "请选择要删除的数据"})
        try:
            ids = [int(x) for x in ids_str.split(",")]
        except Exception:
            return self.write({"code": 1, "msg": "数据ID格式错误"})

        if OutlookDataRepository.delete_data(ids):
            return self.write({"code": 0, "msg": "删除成功"})
        return self.write({"code": 1, "msg": "删除失败"})

class AdminOutlookCollectPageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = OutlookSourceRepository.get_active_sources()
        self.render("admin/outlook_collect.html", title="瞭望采集", username=self.current_user, current_page='outlook_collect', sources=sources, sources_json=json.dumps(sources))

class AdminOutlookLatestDataApiHandler(AdminBaseHandler):
    """获取最近一次采集的数据（用于采集页面展示）"""
    @tornado.web.authenticated
    def get(self):
        task_id = self.get_argument("task_id", "")
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "30"))
        offset = (page - 1) * page_size
        task_keyword = ""
        with get_connection() as conn:
            if task_id:
                # 获取任务关键词
                task_row = conn.execute("SELECT keyword FROM outlook_tasks WHERE id=?", (task_id,)).fetchone()
                if task_row:
                    task_keyword = task_row["keyword"]
                count_row = conn.execute("SELECT COUNT(*) as total FROM outlook_data WHERE task_id=?", (task_id,)).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data WHERE task_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (task_id, page_size, offset)
                ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) as total FROM outlook_data").fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data ORDER BY id DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "msg": "",
            "count": total,
            "task_keyword": task_keyword,
            "data": [dict(r) for r in rows]
        })

class AdminOutlookStatusApiHandler(AdminBaseHandler):
    """获取采集过程状态"""
    @tornado.web.authenticated
    def get(self):
        task_id = self.get_argument("task_id", "")
        if not task_id:
            return self.write({"code": 1, "msg": "缺少task_id参数"})
        status = get_collect_status(task_id)
        if not status:
            return self.write({"code": 0, "msg": "未找到状态信息", "data": {}})
        elapsed = time.time() - status.get('start_time', time.time())
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        status['elapsed'] = f"{minutes:02d}:{seconds:02d}"
        total_count = status.get('total_count', 0)
        status['speed'] = round(total_count / elapsed, 1) if elapsed > 0 else 0
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": status})
