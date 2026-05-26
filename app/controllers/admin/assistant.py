import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.assistant import AssistantRepository, ChatHistoryRepository
from app.models.model import ModelRepository


class AdminAssistantConfigHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/assistant.html", title="数字员工", username=self.current_user, current_page="biz_employees")


class AdminAssistantApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "list")
		if action == "detail":
			aid = int(self.get_argument("id", "0"))
			row = AssistantRepository.get_assistant_by_id(aid)
			self.set_header("Content-Type", "application/json")
			self.write({"code": 0, "data": row})
		elif action == "stats":
			days = int(self.get_argument("days", "7"))
			result = AssistantRepository.get_usage_stats(days=days)
			self.set_header("Content-Type", "application/json")
			self.write({"code": 0, "data": result})
		elif action == "models":
			rows = ModelRepository.get_model_list(page_size=100)
			self.write({"code": 0, "data": rows.get("data", [])})
		elif action == "apis":
			from app.models.api import ApiRepository
			rows = ApiRepository.get_api_list(page_size=200)
			self.write({"code": 0, "data": rows.get("data", [])})
		else:
			page = int(self.get_argument("page", "1"))
			limit = self.get_argument("limit", None)
			page_size = int(limit) if limit else int(self.get_argument("page_size", "20"))
			keyword = self.get_argument("keyword", None)
			result = AssistantRepository.get_assistant_list(page=page, page_size=page_size, keyword=keyword)
			self.set_header("Content-Type", "application/json")
			self.write({"code": 0, "msg": "", "count": result["total"], "data": result["data"]})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "add")
		common_data = {
			"assistant_name": self.get_body_argument("assistant_name"),
			"assistant_code": self.get_body_argument("assistant_code"),
			"prompt_template": self.get_body_argument("prompt_template", ""),
			"icon": self.get_body_argument("icon", "layui-icon-user"),
			"sort_order": int(self.get_body_argument("sort_order", "0")),
			"is_enabled": int(self.get_body_argument("is_enabled", "1")),
			"api_key": self.get_body_argument("api_key", ""),
			"api_url": self.get_body_argument("api_url", ""),
			"description": self.get_body_argument("description", ""),
			"category": self.get_body_argument("category", "AI"),
		}
		mid = self.get_body_argument("model_id", "0")
		common_data["model_id"] = int(mid) if mid and mid != "0" else None
		api_id = self.get_body_argument("api_interface_id", "0")
		common_data["api_interface_id"] = int(api_id) if api_id and api_id != "0" else None

		if action == "edit":
			aid = int(self.get_body_argument("id", "0"))
			if AssistantRepository.update_assistant(aid, common_data):
				self.write({"code": 0, "msg": "修改成功"})
			else:
				self.write({"code": 1, "msg": "修改失败"})
		elif action == "sort":
			ids = json.loads(self.get_body_argument("ids", "[]"))
			if AssistantRepository.update_sort_order(ids):
				self.write({"code": 0, "msg": "排序成功"})
			else:
				self.write({"code": 1, "msg": "排序失败"})
		else:
			if AssistantRepository.add_assistant(common_data):
				self.write({"code": 0, "msg": "添加成功"})
			else:
				self.write({"code": 1, "msg": "添加失败"})

	@tornado.web.authenticated
	def delete(self):
		aid = int(self.get_argument("id", "0"))
		if AssistantRepository.delete_assistant(aid):
			self.write({"code": 0, "msg": "删除成功"})
		else:
			self.write({"code": 1, "msg": "删除失败"})


class AdminAssistantChatHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		assistants = AssistantRepository.get_enabled_assistants()
		self.render("admin/agent_chat.html", title="对话", username=self.current_user, assistants=assistants, current_page="biz_employees")


class AdminAssistantUsageHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/assistant_usage.html", title="使用统计", username=self.current_user, current_page="biz_employees")


class AdminChatSendHandler(AdminBaseHandler):
	@tornado.web.authenticated
	async def post(self):
		content = self.get_body_argument("content", "").strip()
		assistant_id = int(self.get_body_argument("assistant_id", "0"))
		if not content:
			self.set_header("Content-Type", "application/json")
			self.write({"code": 1, "msg": "内容不能为空"})
			return
		assistant = AssistantRepository.get_assistant_by_id(assistant_id)
		if not assistant:
			self.set_header("Content-Type", "application/json")
			self.write({"code": 1, "msg": "助手不存在"})
			return
		prompt_template = assistant.get("prompt_template", "")
		if prompt_template:
			messages = [{"role": "system", "content": prompt_template}, {"role": "user", "content": content}]
		else:
			messages = [{"role": "user", "content": content}]
		model_id = assistant.get("model_id")
		model = None
		if model_id:
			model = ModelRepository.get_model_by_id(model_id)
		if not model:
			model = ModelRepository.get_default_model()
		if not model:
			self.set_header("Content-Type", "application/json")
			self.write({"code": 1, "msg": "没有可用模型"})
			return
		user_id = self._get_admin_user_id()
		ChatHistoryRepository.save_message(user_id, assistant_id, model.get("id"), "user", content)
		self.set_header("Content-Type", "text/event-stream")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")
		self.set_header("X-Accel-Buffering", "no")
		full_response = ""
		try:
			import httpx
			api_headers = {"Authorization": f"Bearer {model.get('api_key','')}", "Content-Type": "application/json"}
			payload = {"model": model.get("code",""), "messages": messages, "stream": True}
			api_url = model.get("api_url","")
			with httpx.Client(timeout=120.0) as client:
				with client.stream("POST", api_url, headers=api_headers, json=payload) as response:
					if response.status_code != 200:
						err_text = ""
						try:
							err_text = response.read().decode("utf-8", errors="replace")[:300]
						except Exception:
							pass
						self.write(f"data: {json.dumps({'error': f'API Error {response.status_code}: {err_text}'}, ensure_ascii=False)}\n\n")
						await self.flush()
						await self.finish()
						return
					for line in response.iter_lines():
						if not line:
							continue
						if line.startswith("data: "):
							data_str = line[6:]
							if data_str == "[DONE]":
								break
							try:
								block = json.loads(data_str)
								delta = block.get("choices", [{}])[0].get("delta", {})
								chunk = delta.get("content", "")
								if chunk:
									full_response += chunk
									self.write(f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n")
									await self.flush()
							except Exception:
								continue
			if full_response:
				ChatHistoryRepository.save_message(user_id, assistant_id, model.get("id"), "assistant", full_response)
			self.write("data: [DONE]\n\n")
		except Exception as e:
			self.write(f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n")
		await self.finish()

	def _get_admin_user_id(self):
		from app.models.db import get_connection
		with get_connection() as conn:
			user = conn.execute("SELECT id FROM users WHERE username=?", (self.current_user,)).fetchone()
		return user["id"] if user else 0


class AdminChatHistoryHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		from app.models.db import get_connection
		with get_connection() as conn:
			user = conn.execute("SELECT id FROM users WHERE username=?", (self.current_user,)).fetchone()
		user_id = user["id"] if user else 0
		assistant_id = self.get_argument("assistant_id", None)
		if assistant_id:
			assistant_id = int(assistant_id)
		messages = ChatHistoryRepository.get_history(user_id, assistant_id)
		self.write({"code": 0, "data": messages})


class AdminChatClearHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		from app.models.db import get_connection
		with get_connection() as conn:
			user = conn.execute("SELECT id FROM users WHERE username=?", (self.current_user,)).fetchone()
		user_id = user["id"] if user else 0
		assistant_id = self.get_body_argument("assistant_id", None)
		if assistant_id:
			assistant_id = int(assistant_id)
		ChatHistoryRepository.clear_history(user_id, assistant_id)
		self.write({"code": 0, "msg": "已清空"})
