import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.db import get_connection


class DashboardPageHandler(tornado.web.RequestHandler):
	def get(self):
		self.render("admin/dashboard.html", title="数智大屏")


class DashboardStatsHandler(tornado.web.RequestHandler):
	def get(self):
		with get_connection() as conn:
			today = conn.execute(
				"SELECT COUNT(*) as cnt FROM outlook_data WHERE date(create_at)=date('now')"
			).fetchone()["cnt"]
			total = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data").fetchone()["cnt"]
			sources = conn.execute("SELECT COUNT(*) as cnt FROM outlook_sources WHERE status=1").fetchone()["cnt"]
			tasks = conn.execute("SELECT COUNT(*) as cnt FROM outlook_tasks").fetchone()["cnt"]
			fail_count = conn.execute(
				"SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='error'"
			).fetchone()["cnt"]
			process_count = conn.execute(
				"SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='running'"
			).fetchone()["cnt"]
			recent = conn.execute(
				"SELECT title, create_at FROM outlook_data ORDER BY id DESC LIMIT 10"
			).fetchall()
		self.set_header("Content-Type", "application/json")
		self.write({
			"code": 0,
			"data": {
				"today_collect": today,
				"total_collect": total,
				"data_source": sources,
				"total_tasks": tasks,
				"fail_count": fail_count,
				"process_count": process_count,
				"recent": [dict(r) for r in recent],
			}
		})


class DashboardComponentsHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/dashboard_components.html", title="组件管理", username=self.current_user, current_page="biz_dashboard_components")


class DashboardComponentAPIHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM dashboard_components ORDER BY sort_order ASC, id ASC"
			).fetchall()
		self.set_header("Content-Type", "application/json")
		self.write({"code": 0, "data": [dict(r) for r in rows]})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "add")
		if action == "edit":
			cid = int(self.get_body_argument("id", "0"))
			data = {
				"name": self.get_body_argument("name"),
				"type": self.get_body_argument("type", "line"),
				"color": self.get_body_argument("color", "#1890ff"),
				"refresh_interval": int(self.get_body_argument("refresh_interval", "30")),
				"grid_x": int(self.get_body_argument("grid_x", "0")),
				"grid_y": int(self.get_body_argument("grid_y", "0")),
				"grid_w": int(self.get_body_argument("grid_w", "4")),
				"grid_h": int(self.get_body_argument("grid_h", "4")),
				"is_enabled": int(self.get_body_argument("is_enabled", "1")),
				"sort_order": int(self.get_body_argument("sort_order", "0")),
			}
			self._update_component(cid, data)
		else:
			data = {
				"name": self.get_body_argument("name"),
				"type": self.get_body_argument("type", "line"),
				"color": self.get_body_argument("color", "#1890ff"),
				"refresh_interval": int(self.get_body_argument("refresh_interval", "30")),
				"grid_x": int(self.get_body_argument("grid_x", "0")),
				"grid_y": int(self.get_body_argument("grid_y", "0")),
				"grid_w": int(self.get_body_argument("grid_w", "4")),
				"grid_h": int(self.get_body_argument("grid_h", "4")),
				"is_enabled": int(self.get_body_argument("is_enabled", "1")),
				"sort_order": int(self.get_body_argument("sort_order", "0")),
			}
			self._add_component(data)

	def _add_component(self, data):
		try:
			with get_connection() as conn:
				conn.execute(
					"INSERT INTO dashboard_components(name,type,color,refresh_interval,grid_x,grid_y,grid_w,grid_h,is_enabled,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?)",
					(data["name"], data["type"], data["color"], data["refresh_interval"],
					 data["grid_x"], data["grid_y"], data["grid_w"], data["grid_h"],
					 data["is_enabled"], data["sort_order"])
				)
			self.write({"code": 0, "msg": "添加成功"})
		except Exception as e:
			self.write({"code": 1, "msg": f"失败: {e}"})

	def _update_component(self, cid, data):
		try:
			with get_connection() as conn:
				conn.execute(
					"""UPDATE dashboard_components SET name=?,type=?,color=?,refresh_interval=?,
					grid_x=?,grid_y=?,grid_w=?,grid_h=?,is_enabled=?,sort_order=? WHERE id=?""",
					(data["name"], data["type"], data["color"], data["refresh_interval"],
					 data["grid_x"], data["grid_y"], data["grid_w"], data["grid_h"],
					 data["is_enabled"], data["sort_order"], cid)
				)
			self.write({"code": 0, "msg": "修改成功"})
		except Exception as e:
			self.write({"code": 1, "msg": f"失败: {e}"})

	@tornado.web.authenticated
	def delete(self):
		cid = int(self.get_argument("id", "0"))
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM dashboard_components WHERE id=?", (cid,))
			self.write({"code": 0, "msg": "删除成功"})
		except Exception as e:
			self.write({"code": 1, "msg": f"失败: {e}"})
