import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.api import ApiRepository


class AdminApiListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render(
            "admin/api_list.html",
            title="接口管理",
            username=self.current_user,
            current_page="data_api"
        )


class AdminApiListApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        limit_param = self.get_argument("limit", None)
        page_size = int(limit_param) if limit_param else int(self.get_argument("page_size", "20"))
        keyword = self.get_argument("keyword", "")
        result = ApiRepository.get_api_list(
            page=page,
            page_size=page_size,
            keyword=keyword if keyword else None
        )
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["data"]
        })


class AdminApiAddHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        api_url = (self.get_body_argument("api_url", "") or "").strip()
        method = (self.get_body_argument("method", "GET") or "GET").upper()
        response_format = (self.get_body_argument("response_format", "JSON") or "JSON").upper()
        request_example = (self.get_body_argument("request_example", "") or "").strip()
        params_schema = (self.get_body_argument("params_schema", "") or "").strip()
        headers = (self.get_body_argument("headers", "") or "").strip()
        description = (self.get_body_argument("description", "") or "").strip()
        qps_limit = (self.get_body_argument("qps_limit", "") or "").strip()
        status = int(self.get_body_argument("status", "1"))

        if not name or not code or not api_url:
            return self.write({"code": 1, "msg": "接口名称、编码和地址不能为空"})

        if ApiRepository.create_api(
            name, code, api_url, method, response_format,
            request_example, params_schema, headers, description, qps_limit, status
        ):
            return self.write({"code": 0, "msg": "新增成功"})
        return self.write({"code": 1, "msg": "新增失败，编码可能已存在"})


class AdminApiEditHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        api_id = int(self.get_body_argument("id", "0"))
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        api_url = (self.get_body_argument("api_url", "") or "").strip()
        method = (self.get_body_argument("method", "GET") or "GET").upper()
        response_format = (self.get_body_argument("response_format", "JSON") or "JSON").upper()
        request_example = (self.get_body_argument("request_example", "") or "").strip()
        params_schema = (self.get_body_argument("params_schema", "") or "").strip()
        headers = (self.get_body_argument("headers", "") or "").strip()
        description = (self.get_body_argument("description", "") or "").strip()
        qps_limit = (self.get_body_argument("qps_limit", "") or "").strip()
        status = int(self.get_body_argument("status", "1"))

        if not api_id:
            return self.write({"code": 1, "msg": "接口ID不能为空"})
        if not name or not code or not api_url:
            return self.write({"code": 1, "msg": "接口名称、编码和地址不能为空"})

        if ApiRepository.update_api(
            api_id, name=name, code=code, api_url=api_url, method=method,
            response_format=response_format, request_example=request_example,
            params_schema=params_schema, headers=headers, description=description,
            qps_limit=qps_limit, status=status
        ):
            return self.write({"code": 0, "msg": "修改成功"})
        return self.write({"code": 1, "msg": "修改失败"})


class AdminApiDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        api_id = int(self.get_body_argument("id", "0"))
        if not api_id:
            return self.write({"code": 1, "msg": "接口ID不能为空"})
        if ApiRepository.delete_api(api_id):
            return self.write({"code": 0, "msg": "删除成功"})
        return self.write({"code": 1, "msg": "删除失败"})


class AdminApiTestHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        api_id = int(self.get_body_argument("api_id", "0"))
        params_raw = self.get_body_argument("params", "") or "{}"
        try:
            params = json.loads(params_raw) if params_raw else {}
            if not isinstance(params, dict):
                params = {}
        except json.JSONDecodeError:
            return self.write({"code": 1, "msg": "参数格式错误，请使用 JSON 对象"})

        if not api_id:
            return self.write({"code": 1, "msg": "接口ID不能为空"})

        result = ApiRepository.test_api(api_id, params)
        if result.get("success"):
            return self.write({"code": 0, "msg": "调用成功", "data": result})
        return self.write({"code": 1, "msg": result.get("error", "调用失败"), "data": result})


class AdminApiServiceHandler(AdminBaseHandler):
    """统一 API 服务入口，供系统其他模块 HTTP 调用"""

    @tornado.web.authenticated
    def get(self):
        code = (self.get_argument("code", "") or "").strip()
        if not code:
            return self.write({"code": 1, "msg": "缺少参数 code"})

        params = {}
        for key in self.request.arguments:
            if key not in ("code", "_xsrf"):
                params[key] = self.get_argument(key)

        result = ApiRepository.invoke(code, params)
        self.set_header("Content-Type", "application/json")
        if result.get("success"):
            self.write({"code": 0, "msg": "ok", "data": result})
        else:
            self.write({"code": 1, "msg": result.get("error", "调用失败"), "data": result})

    @tornado.web.authenticated
    def post(self):
        code = (self.get_body_argument("code", "") or "").strip()
        params_raw = self.get_body_argument("params", "") or "{}"
        if not code:
            return self.write({"code": 1, "msg": "缺少参数 code"})
        try:
            params = json.loads(params_raw) if params_raw else {}
            if not isinstance(params, dict):
                params = {}
        except json.JSONDecodeError:
            return self.write({"code": 1, "msg": "params 须为 JSON 对象"})

        result = ApiRepository.invoke(code, params)
        self.set_header("Content-Type", "application/json")
        if result.get("success"):
            self.write({"code": 0, "msg": "ok", "data": result})
        else:
            self.write({"code": 1, "msg": result.get("error", "调用失败"), "data": result})
