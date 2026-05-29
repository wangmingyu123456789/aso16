import json
import time
import threading
import tornado.web
from app.controllers.base import BaseHandler
from app.models.outlook import OutlookSourceRepository, OutlookDataRepository, OutlookTaskRepository, OutlookCollector, OutlookDeepCollectRepository, CrawlLogRepository, CrawlScheduleRepository
from app.models.db import get_connection
from app.models import crawl_scheduler

_collect_status = {}
_status_lock = threading.Lock()

def set_collect_status(task_id, status):
    with _status_lock:
        _collect_status[str(task_id)] = {**status, 'update_time': time.time()}

def get_collect_status(task_id):
    with _status_lock:
        return _collect_status.get(str(task_id), {})

def clear_collect_status(task_id):
    with _status_lock:
        _collect_status.pop(str(task_id), None)

class UserOutlookCollectPageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = OutlookSourceRepository.get_active_sources()
        self.render("user/outlook_collect.html", title="瞭望采集", username=self.current_user, sources=sources, sources_json=json.dumps(sources), current_page="outlook_collect")

class UserOutlookCollectHandler(BaseHandler):
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
        url_offset = 0
        for source in selected_sources:
            step = page_size_step if page_size_step > 0 else source.get('page_size_step', 10)
            log_id = CrawlLogRepository.create_log(task_id, source['id'], source['name'], keyword)
            print(f"[Collect-User] source={source['name']}, keyword={keyword}, pages={pages}, step={step}", flush=True)

            status = get_collect_status(task_id)
            status['current_source'] = source['name']
            set_collect_status(task_id, status)

            def make_callback(tid, offset):
                def callback(update):
                    current = get_collect_status(tid)
                    if 'success_count' in update:
                        current['success_count'] = current.get('success_count', 0) + update['success_count']
                    if 'fail_count' in update:
                        current['fail_count'] = current.get('fail_count', 0) + update['fail_count']
                    if 'total_count' in update:
                        current['total_count'] = current.get('total_count', 0) + update['total_count']
                    for k, v in update.items():
                        if k not in ('success_count', 'fail_count', 'total_count'):
                            current[k] = v
                    if 'current_url' in update and offset > 0:
                        current['current_url'] = update['current_url'] + offset
                    set_collect_status(tid, current)
                return callback

            try:
                count = OutlookCollector.collect_with_status(
                    source, keyword, pages, step,
                    use_ai_expand=ai_expand,
                    use_ai_clean=ai_clean,
                    task_id=task_id,
                    status_callback=make_callback(task_id, url_offset)
                )
                total_results += count
                CrawlLogRepository.complete_log(log_id, total_count=count, saved_count=count)
                print(f"[Collect-User] source={source['name']}, saved={count}", flush=True)
            except Exception as e:
                CrawlLogRepository.fail_log(log_id, str(e)[:500])
                print(f"[Collect-User] source={source['name']}, FAILED: {e}", flush=True)
            url_offset += pages

        final_status = get_collect_status(task_id)
        final_status['status'] = 'completed'
        final_status['total_count'] = total_results
        final_status['logs'].append({'time': time.strftime('%H:%M:%S'), 'type': 'success', 'msg': f'采集完成，共获取 {total_results} 条数据'})
        set_collect_status(task_id, final_status)
        OutlookTaskRepository.update_task(task_id, total_results)

        return self.write({"code": 0, "msg": f"采集完成，共获取 {total_results} 条数据", "count": total_results, "task_id": task_id})

class UserOutlookStatusApiHandler(BaseHandler):
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

class UserOutlookLatestDataApiHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        task_id = self.get_argument("task_id", "")
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "30"))
        offset = (page - 1) * page_size
        task_keyword = ""
        with get_connection() as conn:
            if task_id:
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
        self.write({"code": 0, "msg": "", "count": total, "task_keyword": task_keyword, "data": [dict(r) for r in rows]})

class UserOutlookDataListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("user/outlook_data_list.html", title="数据仓库", username=self.current_user, current_page="outlook_data")

class UserOutlookDataApiHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "20"))
        keyword = self.get_argument("keyword", "")
        result = OutlookDataRepository.get_data_list(page=page, page_size=page_size, keyword=keyword if keyword else None)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "msg": "", "count": result["total"], "data": result["data"]})

class UserOutlookTaskApiHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "20"))
        keyword = self.get_argument("keyword", "")
        result = OutlookTaskRepository.get_task_list(page=page, page_size=page_size, keyword=keyword if keyword else None)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "msg": "", "count": result["total"], "data": result["data"]})

class UserOutlookTaskDeleteHandler(BaseHandler):
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
        clear_collect_status(task_id)
        return self.write({"code": 0, "msg": "删除成功"})

class UserOutlookTaskDataHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        task_id = int(self.get_argument("task_id", "0"))
        task = OutlookTaskRepository.get_task(task_id)
        self.render("user/outlook_task_data.html", title="任务数据", username=self.current_user, task=task)

class UserOutlookTaskDataApiHandler(BaseHandler):
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
                    "SELECT * FROM outlook_data WHERE task_id=? AND title LIKE ? ORDER BY create_at ASC LIMIT ? OFFSET ?",
                    (task_id, f'%{keyword}%', page_size, offset)
                ).fetchall()
            else:
                count_row = conn.execute(
                    "SELECT COUNT(*) as total FROM outlook_data WHERE task_id=?",
                    (task_id,)
                ).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    "SELECT * FROM outlook_data WHERE task_id=? ORDER BY create_at ASC LIMIT ? OFFSET ?",
                    (task_id, page_size, offset)
                ).fetchall()
        self.set_header("Content-Type", "application/json")
        data_list = []
        for i, r in enumerate(rows):
            d = dict(r)
            d["_seq"] = offset + i + 1
            deep_row = conn.execute(
                "SELECT status FROM outlook_data_detail WHERE data_id=? ORDER BY id DESC LIMIT 1",
                (d['id'],)
            ).fetchone()
            d['deep_status'] = deep_row['status'] if deep_row else None
            data_list.append(d)
        self.write({"code": 0, "msg": "", "count": total, "data": data_list})

class UserOutlookDeepCollectHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        data_ids_str = self.get_body_argument("data_ids", "")
        if not data_ids_str:
            return self.write({"code": 1, "msg": "请选择要深度采集的数据"})
        try:
            data_ids = [int(x.strip()) for x in data_ids_str.split(",") if x.strip()]
        except ValueError:
            return self.write({"code": 1, "msg": "数据ID格式错误"})
        if not data_ids:
            return self.write({"code": 1, "msg": "请选择要深度采集的数据"})

        import uuid
        task_id = str(uuid.uuid4())[:8]
        logs = []
        OutlookDeepCollectRepository.set_progress(task_id, {
            "task_id": task_id, "total": len(data_ids), "current": 0,
            "status": "running", "logs": logs, "success": 0, "failed": 0
        })

        def progress_callback(current, total, log_msg, data_id, status):
            progress = OutlookDeepCollectRepository.get_progress(task_id)
            if progress:
                progress["current"] = current
                progress["logs"].append({"msg": log_msg, "status": status, "data_id": data_id})
                if status == "success":
                    progress["success"] += 1
                elif status == "failed":
                    progress["failed"] += 1

        def run_deep_collect():
            try:
                result = OutlookDeepCollectRepository.deep_collect(data_ids, callback=progress_callback)
                progress = OutlookDeepCollectRepository.get_progress(task_id)
                if progress:
                    progress["status"] = "completed"
                    progress["result"] = result
            except Exception as e:
                progress = OutlookDeepCollectRepository.get_progress(task_id)
                if progress:
                    progress["status"] = "error"
                    progress["error"] = str(e)

        thread = threading.Thread(target=run_deep_collect, daemon=True)
        thread.start()
        return self.write({"code": 0, "msg": "深度采集已启动", "task_id": task_id})

class UserOutlookDeepCollectStatusHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        task_id = self.get_argument("task_id", "")
        if not task_id:
            return self.write({"code": 1, "msg": "缺少task_id参数"})
        progress = OutlookDeepCollectRepository.get_progress(task_id)
        if not progress:
            return self.write({"code": 1, "msg": "未找到采集任务"})
        return self.write({"code": 0, "data": progress})

class UserOutlookDeepDetailHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        data_id = int(self.get_argument("data_id", "0"))
        if not data_id:
            return self.write({"code": 1, "msg": "缺少data_id参数"})
        detail = OutlookDeepCollectRepository.get_detail_by_data_id(data_id)
        if not detail:
            return self.write({"code": 1, "msg": "未找到深度采集结果"})
        return self.write({"code": 0, "data": detail})

class UserOutlookSourceApiHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = OutlookSourceRepository.get_all_sources()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": sources})

class UserOutlookSourceAddHandler(BaseHandler):
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

class UserOutlookSourceEditHandler(BaseHandler):
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

class UserOutlookSourceDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        source_id = int(self.get_body_argument("id", "0"))
        if not source_id:
            return self.write({"code": 1, "msg": "数据源ID不能为空"})
        if OutlookSourceRepository.delete_source(source_id):
            return self.write({"code": 0, "msg": "删除成功"})
        return self.write({"code": 1, "msg": "删除失败"})

class UserOutlookDataDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids_str = self.get_body_argument("ids", "")
        if not ids_str:
            return self.write({"code": 1, "msg": "请选择要删除的数据"})
        try:
            ids = [int(x) for x in ids_str.split(",")]
        except Exception:
            return self.write({"code": 1, "msg": "数据ID格式错误"})
        if OutlookDataRepository.delete_data_batch(ids):
            return self.write({"code": 0, "msg": "删除成功"})
        return self.write({"code": 1, "msg": "删除失败"})

class UserCrawlLogHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("user/crawl_log.html", title="采集日志", username=self.current_user, current_page="outlook_log")

class UserCrawlLogApiHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        limit = self.get_argument("limit", None)
        page_size = int(limit) if limit else int(self.get_argument("page_size", "20"))
        result = CrawlLogRepository.get_log_list(page=page, page_size=page_size)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "msg": "", "count": result["total"], "data": result["data"]})

class UserCrawlLogClearHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        CrawlLogRepository.clear_all_logs()
        self.write({"code": 0, "msg": "日志已清空"})

class UserCrawlScheduleHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("user/crawl_schedule.html", title="定时采集", username=self.current_user, current_page="outlook_schedule")

class UserCrawlScheduleApiHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "list")
        if action == "detail":
            sid = int(self.get_argument("id", "0"))
            row = CrawlScheduleRepository.get_schedule_by_id(sid)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "data": row})
        elif action == "sources":
            sources = OutlookSourceRepository.get_active_sources()
            self.write({"code": 0, "data": sources})
        else:
            page = int(self.get_argument("page", "1"))
            limit = self.get_argument("limit", None)
            page_size = int(limit) if limit else int(self.get_argument("page_size", "20"))
            result = CrawlScheduleRepository.get_schedule_list(page=page, page_size=page_size)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "msg": "", "count": result["total"], "data": result["data"]})

    @tornado.web.authenticated
    def post(self):
        action = self.get_argument("action", "add")
        if action == "edit":
            sid = int(self.get_body_argument("id", "0"))
            data = {
                "source_id": int(self.get_body_argument("source_id", "0")),
                "source_name": self.get_body_argument("source_name", ""),
                "keyword": self.get_body_argument("keyword", ""),
                "cron_expression": self.get_body_argument("cron_expression", ""),
                "sch_year": int(self.get_body_argument("sch_year", "0")),
                "pages": int(self.get_body_argument("pages", "1")),
                "per_page": int(self.get_body_argument("per_page", "10")),
                "is_enabled": int(self.get_body_argument("is_enabled", "1")),
            }
            if CrawlScheduleRepository.update_schedule(sid, **data):
                crawl_scheduler.reload_schedules()
                self.write({"code": 0, "msg": "修改成功"})
            else:
                self.write({"code": 1, "msg": "修改失败"})
        else:
            if CrawlScheduleRepository.add_schedule(
                source_id=int(self.get_body_argument("source_id", "0")),
                source_name=self.get_body_argument("source_name", ""),
                keyword=self.get_body_argument("keyword", ""),
                cron_expression=self.get_body_argument("cron_expression", ""),
                sch_year=int(self.get_body_argument("sch_year", "0")),
                pages=int(self.get_body_argument("pages", "1")),
                per_page=int(self.get_body_argument("per_page", "10")),
                is_enabled=int(self.get_body_argument("is_enabled", "1")),
            ):
                crawl_scheduler.reload_schedules()
                self.write({"code": 0, "msg": "添加成功"})
            else:
                self.write({"code": 1, "msg": "添加失败"})

    @tornado.web.authenticated
    def delete(self):
        ids_param = self.get_argument("ids", None)
        if ids_param:
            ids = [int(x) for x in ids_param.split(",") if x.strip()]
            if CrawlScheduleRepository.batch_delete(ids):
                crawl_scheduler.reload_schedules()
                self.write({"code": 0, "msg": "批量删除成功"})
            else:
                self.write({"code": 1, "msg": "批量删除失败"})
        else:
            sid = int(self.get_argument("id", "0"))
            if CrawlScheduleRepository.delete_schedule(sid):
                crawl_scheduler.reload_schedules()
                self.write({"code": 0, "msg": "删除成功"})
            else:
                self.write({"code": 1, "msg": "删除失败"})
