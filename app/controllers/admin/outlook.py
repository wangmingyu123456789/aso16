import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.outlook import OutlookSourceRepository, OutlookDataRepository, OutlookCollector

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

        total_results = 0
        for source in selected_sources:
            step = page_size_step if page_size_step > 0 else source.get('page_size_step', 10)
            print(f"[Collect] source={source['name']}, keyword={keyword}, pages={pages}, step={step}")
            count = OutlookCollector.collect(
                source, keyword, pages, step,
                use_ai_expand=ai_expand,
                use_ai_clean=ai_clean
            )
            total_results += count
            print(f"[Collect] source={source['name']}, saved={count}")

        return self.write({
            "code": 0,
            "msg": f"采集完成，共获取 {total_results} 条数据",
            "data": {"count": total_results}
        })

class AdminOutlookDataListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/outlook_data_list.html", title="数据仓库", username=self.current_user, current_page='outlook_data')

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
