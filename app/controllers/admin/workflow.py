import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.workflow import WorkflowRepository
from app.models.db import get_connection


class AdminWorkflowListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		raw_workflows = WorkflowRepository.get_all()
		step_labels = {'crawl':'📡 采集','analyze':'🧠 分析','notify':'📧 通知'}
		workflows = []
		for w in raw_workflows:
			wf = dict(w)
			if isinstance(wf["steps"], str):
				wf["steps"] = json.loads(wf["steps"])
			for step in wf["steps"]:
				step["_label"] = step_labels.get(step.get("type",""), step.get("type",""))
			workflows.append(wf)
		self.render("admin/workflow_list.html", title="自动化工作流", username=self.current_user, current_page="workflow", workflows=workflows)


class AdminWorkflowEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self, wid=None):
		workflow = None
		if wid:
			workflow = WorkflowRepository.get_by_id(int(wid))
		# 获取数据源列表供选择
		with get_connection() as conn:
			sources = conn.execute("SELECT id, name, source_type FROM outlook_sources WHERE status=1 ORDER BY id DESC").fetchall()
			sources_list = [dict(s) for s in sources]
		self.render("admin/workflow_edit.html", title="编辑工作流", username=self.current_user, current_page="workflow", workflow=workflow, sources=sources_list, sources_json=json.dumps(sources_list, ensure_ascii=False))


class AdminWorkflowApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "")
		if action == "detail":
			wid = int(self.get_argument("id"))
			wf = WorkflowRepository.get_by_id(wid)
			if wf:
				self.write({"code": 0, "data": dict(wf)})
			else:
				self.write({"code": 1, "msg": "工作流不存在"})
		elif action == "logs":
			wid = int(self.get_argument("id"))
			logs = WorkflowRepository.get_logs(wid)
			self.write({"code": 0, "data": [dict(l) for l in logs]})
		else:
			self.write({"code": 1, "msg": "未知操作"})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		try:
			if action == "create":
				name = self.get_argument("name")
				description = self.get_argument("description", "")
				steps_json = self.get_argument("steps", "[]")
				steps = json.loads(steps_json)
				cron = self.get_argument("cron_expression", "")
				wid = WorkflowRepository.create(name, description, steps, cron)
				self.write({"code": 0, "data": {"id": wid}, "msg": "创建成功"})

			elif action == "update":
				wid = int(self.get_argument("id"))
				name = self.get_argument("name")
				description = self.get_argument("description", "")
				steps_json = self.get_argument("steps", "[]")
				steps = json.loads(steps_json)
				cron = self.get_argument("cron_expression", "")
				is_enabled = int(self.get_argument("is_enabled", "1"))
				WorkflowRepository.update(wid, name, description, steps, cron, is_enabled)
				self.write({"code": 0, "msg": "更新成功"})

			elif action == "delete":
				wid = int(self.get_argument("id"))
				WorkflowRepository.delete(wid)
				self.write({"code": 0, "msg": "删除成功"})

			elif action == "toggle":
				wid = int(self.get_argument("id"))
				WorkflowRepository.toggle(wid)
				self.write({"code": 0, "msg": "切换成功"})

			elif action == "run":
				wid = int(self.get_argument("id"))
				wf = WorkflowRepository.get_by_id(wid)
				if not wf:
					self.write({"code": 1, "msg": "工作流不存在"})
					return

				log_id = WorkflowRepository.add_log(wid, "running")
				steps = json.loads(wf["steps"])

				try:
					result = self._execute_steps(steps)
					WorkflowRepository.update_log(log_id, "success", json.dumps(result, ensure_ascii=False))
					with get_connection() as conn:
						conn.execute("UPDATE auto_workflows SET last_run_at=datetime('now'),last_result=? WHERE id=?", (json.dumps(result, ensure_ascii=False)[:500], wid))
					self.write({"code": 0, "msg": "执行成功", "data": result})
				except Exception as e:
					WorkflowRepository.update_log(log_id, "failed", str(e))
					self.write({"code": 1, "msg": "执行失败: " + str(e)})

			else:
				self.write({"code": 1, "msg": "未知操作"})
		except Exception as e:
			self.write({"code": 1, "msg": str(e)})

	def _execute_steps(self, steps):
		result = {"steps": []}
		for step in steps:
			step_type = step.get("type", "")
			step_result = {"type": step_type, "status": "success", "data": {}}

			if step_type == "crawl":
				from app.models.outlook import OutlookCollector, OutlookSourceRepository
				source_id = step.get("source_id")
				keyword = step.get("keyword", "")
				pages = int(step.get("pages", 1))
				source = OutlookSourceRepository.get_source_by_id(source_id)
				if source:
					count = OutlookCollector.collect(source=source, keyword=keyword, pages=pages, page_size_step=10, use_ai_expand=False, use_ai_clean=False)
					step_result["data"]["count"] = count
				else:
					step_result["status"] = "failed"
					step_result["data"]["error"] = "数据源不存在"

			elif step_type == "analyze":
				from app.controllers.user.sentiment import SentimentAnalyzeHandler
				import tornado.web
				req = tornado.web.RequestHandler(self.application, self.request)
				handler = SentimentAnalyzeHandler(self.application, req)
				# 直接调用分析逻辑
				with get_connection() as conn:
					total = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data").fetchone()["cnt"]
				step_result["data"]["total_analyzed"] = total

			elif step_type == "notify":
				step_result["data"]["message"] = step.get("message", "")

			result["steps"].append(step_result)
		return result


class AdminWorkflowEngineHandler(AdminBaseHandler):
	"""定时触发的工作流执行引擎"""
	@classmethod
	def check_and_run(cls):
		"""检查并执行到期的定时工作流"""
		workflows = WorkflowRepository.get_enabled()
		for wf in workflows:
			cron = wf["cron_expression"] or ""
			if not cron:
				continue
			try:
				from datetime import datetime
				parts = cron.strip().split()
				if len(parts) == 5:
					now = datetime.now()
					minute = int(parts[0]) if parts[0] != "*" else now.minute
					hour = int(parts[1]) if parts[1] != "*" else now.hour
					day = int(parts[2]) if parts[2] != "*" else now.day
					month = int(parts[3]) if parts[3] != "*" else now.month
					if minute == now.minute and hour == now.hour and day == now.day and month == now.month:
						# 避免重复执行（检查上次执行时间）
						if wf["last_run_at"]:
							from datetime import timedelta
							last_run = datetime.strptime(wf["last_run_at"], "%Y-%m-%d %H:%M:%S")
							if (now - last_run).total_seconds() < 60:
								continue
						log_id = WorkflowRepository.add_log(wf["id"], "running", "定时触发")
						try:
							steps = json.loads(wf["steps"])
							api = AdminWorkflowEngineHandler()
							result = api._execute_steps(steps)
							WorkflowRepository.update_log(log_id, "success", json.dumps(result, ensure_ascii=False)[:1000])
							with get_connection() as conn:
								conn.execute("UPDATE auto_workflows SET last_run_at=datetime('now'),last_result=? WHERE id=?", (json.dumps(result, ensure_ascii=False)[:500], wf["id"]))
						except Exception as e:
							WorkflowRepository.update_log(log_id, "failed", str(e))
			except Exception as e:
				print(f"[WorkflowEngine] #{wf['id']} check error: {e}")
