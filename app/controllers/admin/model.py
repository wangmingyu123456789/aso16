import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.model import ModelRepository

class AdminModelListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/model_list.html", title="模型引擎", username=self.current_user, current_page='models')

class AdminModelApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("page_size", "6"))
        keyword = self.get_argument("keyword", "")
        result = ModelRepository.get_model_list(page=page, page_size=page_size, keyword=keyword if keyword else None)
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["data"]
        })

class AdminModelAddHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        api_url = (self.get_body_argument("api_url", "") or "").strip()
        api_key = (self.get_body_argument("api_key", "") or "").strip()
        status = int(self.get_body_argument("status", "1"))

        if not name or not code:
            return self.write({"code": 1, "msg": "模型名称和编码不能为空"})
        if not api_url:
            api_url = "https://aigc-api.aitoolcore.com/api/v1/chat/completions"
        if not api_key:
            api_key = "sk-aigc-c0725a1b8a1b205154867945a3c667ce9d232fa7"

        if ModelRepository.create_model(name, code, api_url, api_key, status):
            return self.write({"code": 0, "msg": "新增成功"})
        return self.write({"code": 1, "msg": "新增失败，模型编码可能已存在"})

class AdminModelEditHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = int(self.get_body_argument("id", "0"))
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        api_url = (self.get_body_argument("api_url", "") or "").strip()
        api_key = self.get_body_argument("api_key", "")
        status = int(self.get_body_argument("status", "1"))

        if not model_id:
            return self.write({"code": 1, "msg": "模型ID不能为空"})
        if not name or not code:
            return self.write({"code": 1, "msg": "模型名称和编码不能为空"})

        if ModelRepository.update_model(model_id, name=name, code=code, api_url=api_url, api_key=api_key, status=status):
            return self.write({"code": 0, "msg": "修改成功"})
        return self.write({"code": 1, "msg": "修改失败"})

class AdminModelDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = int(self.get_body_argument("id", "0"))
        if not model_id:
            return self.write({"code": 1, "msg": "模型ID不能为空"})
        if ModelRepository.delete_model(model_id):
            return self.write({"code": 0, "msg": "删除成功"})
        return self.write({"code": 1, "msg": "删除失败"})

class AdminModelSetDefaultHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = int(self.get_body_argument("id", "0"))
        if not model_id:
            return self.write({"code": 1, "msg": "模型ID不能为空"})
        if ModelRepository.set_default_model(model_id):
            return self.write({"code": 0, "msg": "系统默认模型设置成功"})
        return self.write({"code": 1, "msg": "设置失败"})

class AdminModelChatTestHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        model_id = int(self.get_body_argument("model_id", "0"))
        message = (self.get_body_argument("message", "") or "").strip()

        if not model_id:
            return self.write({"code": 1, "msg": "模型ID不能为空"})
        if not message:
            return self.write({"code": 1, "msg": "请输入测试消息"})

        model = ModelRepository.get_model_by_id(model_id)
        if not model:
            return self.write({"code": 1, "msg": "模型不存在"})
        if model["status"] != 1:
            return self.write({"code": 1, "msg": "模型已禁用"})

        result = ModelRepository.test_model_chat(
            api_url=model["api_url"],
            api_key=model["api_key"],
            model_code=model["code"],
            messages=[{"role": "user", "content": message}]
        )

        if result["success"]:
            ModelRepository.update_token_stats(
                model_id,
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"]
            )
            return self.write({
                "code": 0,
                "msg": "测试成功",
                "data": {
                    "content": result["content"],
                    "usage": result["usage"]
                }
            })
        return self.write({"code": 1, "msg": result.get("error", "测试失败")})

class AdminModelChatStreamHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        import threading
        import queue
        
        model_id = int(self.get_body_argument("model_id", "0"))
        message = (self.get_body_argument("message", "") or "").strip()

        if not model_id:
            return self.write({"code": 1, "msg": "模型ID不能为空"})
        if not message:
            return self.write({"code": 1, "msg": "请输入测试消息"})

        model = ModelRepository.get_model_by_id(model_id)
        if not model:
            return self.write({"code": 1, "msg": "模型不存在"})
        if model["status"] != 1:
            return self.write({"code": 1, "msg": "模型已禁用"})

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("X-Accel-Buffering", "no")
        self.flush()

        q = queue.Queue()
        full_content = ""

        def stream_worker():
            nonlocal full_content
            try:
                for chunk in ModelRepository.stream_model_chat(
                    api_url=model["api_url"],
                    api_key=model["api_key"],
                    model_code=model["code"],
                    messages=[{"role": "user", "content": message}]
                ):
                    q.put(chunk)
            except Exception as e:
                q.put(f'data: {{"error":"{str(e)}"}}\n\n')
            q.put(None)

        threading.Thread(target=stream_worker, daemon=True).start()

        while True:
            try:
                chunk = q.get(timeout=30)
                if chunk is None:
                    break
                self.write(f"data: {chunk}\n\n")
                self.flush()
            except queue.Empty:
                self.write('data: {"error":"请求超时"}\n\n')
                break
            except Exception:
                break

        self.finish()
