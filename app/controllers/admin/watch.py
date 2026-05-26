import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.db import get_connection
from app.models.outlook import CrawlLogRepository, CrawlScheduleRepository
from app.models import crawl_scheduler


class AdminCrawlLogHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/crawl_log.html", title="采集日志", username=self.current_user, current_page="outlook_log")


class AdminCrawlLogApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		limit = self.get_argument("limit", None)
		page_size = int(limit) if limit else int(self.get_argument("page_size", "20"))
		result = CrawlLogRepository.get_log_list(page=page, page_size=page_size)
		self.set_header("Content-Type", "application/json")
		self.write({"code": 0, "msg": "", "count": result["total"], "data": result["data"]})


class AdminCrawlScheduleHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/crawl_schedule.html", title="定时采集", username=self.current_user, current_page="outlook_schedule")


class AdminCrawlScheduleApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "list")
		if action == "detail":
			sid = int(self.get_argument("id", "0"))
			row = CrawlScheduleRepository.get_schedule_by_id(sid)
			self.set_header("Content-Type", "application/json")
			self.write({"code": 0, "data": row})
		elif action == "sources":
			from app.models.outlook import OutlookSourceRepository
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
