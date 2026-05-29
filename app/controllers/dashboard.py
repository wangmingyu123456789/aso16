import json
import sys
import traceback
import datetime
import tornado.web
from app.models.db import get_connection

print(f"[DASHBOARD-MODULE] dashboard.py 模块已加载", flush=True)
tornado.log.app_log.info("[DASHBOARD-MODULE] dashboard.py 模块已加载")


class DashboardPageHandler(tornado.web.RequestHandler):
	def get(self):
		self.render("admin/dashboard.html", title="数智大屏")


class DashboardStatsHandler(tornado.web.RequestHandler):
	def get(self):
		ts = datetime.datetime.now().strftime('%H:%M:%S')
		msg = f"\n{'='*50}\n[DASHBOARD-API {ts}] 收到请求\n客户端IP: {self.request.remote_ip}\n请求参数: {dict(self.request.arguments)}\n{'='*50}"
		print(msg, flush=True)
		tornado.log.app_log.warning(msg)

		self.set_header("Content-Type", "application/json")
		self.set_header("Access-Control-Allow-Origin", "*")

		result = {
			"today_collect": 0,"total_collect": 0,"data_source": 0,
			"total_tasks": 0,"deep_processed": 0,"fail_count": 0,
			"process_count": 0,"recent": [],
		}

		try:
			with get_connection() as conn:
				table_check = conn.execute(
					"SELECT name FROM sqlite_master WHERE type='table' AND name IN ('outlook_data','outlook_sources','outlook_tasks','crawl_logs') ORDER BY name"
				).fetchall()
				existing = [r["name"] for r in table_check]
				print(f"[DASHBOARD-API] 存在的表: {existing}", flush=True)
				for tbl in ["outlook_data","outlook_sources","outlook_tasks","crawl_logs"]:
					if tbl not in existing:
						print(f"[DASHBOARD-API] [警告] 表 {tbl} 不存在!", flush=True)

				sql = "SELECT 'outlook_data' as tn, COUNT(*) as cnt FROM outlook_data UNION ALL SELECT 'outlook_sources', COUNT(*) FROM outlook_sources UNION ALL SELECT 'outlook_tasks', COUNT(*) FROM outlook_tasks UNION ALL SELECT 'crawl_logs', COUNT(*) FROM crawl_logs"
				try:
					for cr in conn.execute(sql).fetchall():
						print(f"[DASHBOARD-API] 表 {cr['tn']}: 总行数={cr['cnt']}", flush=True)
				except Exception as e2:
					print(f"[DASHBOARD-API] 查询表总数失败: {e2}", flush=True)

				row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data WHERE date(create_at,'+8 hours')=date('now','+8 hours')").fetchone()
				today = row["cnt"] if row else 0
				row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data").fetchone()
				total = row["cnt"] if row else 0
				row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_sources WHERE status=1").fetchone()
				sources = row["cnt"] if row else 0
				row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_tasks").fetchone()
				tasks = row["cnt"] if row else 0
				row = conn.execute("SELECT COUNT(*) as cnt FROM outlook_data WHERE ai_deep_status=1").fetchone()
				deep_processed = row["cnt"] if row else 0
				row = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='error'").fetchone()
				fail_count = row["cnt"] if row else 0
				row = conn.execute("SELECT COUNT(*) as cnt FROM crawl_logs WHERE status='running'").fetchone()
				process_count = row["cnt"] if row else 0

				recent_rows = conn.execute(
					"SELECT title, source_name, create_at FROM outlook_data WHERE create_at >= datetime('now','+8 hours','-3 days') ORDER BY id DESC LIMIT 20"
				).fetchall()

				print(f"[DASHBOARD-API] 今日={today} 总计={total} 数据源={sources} 任务={tasks} 深度处理={deep_processed} 失败={fail_count} 处理中={process_count} 最近={len(recent_rows)}条", flush=True)

				result = {
					"today_collect": today,"total_collect": total,"data_source": sources,
					"total_tasks": tasks,"deep_processed": deep_processed,"fail_count": fail_count,
					"process_count": process_count,"recent": [dict(r) for r in recent_rows],
				}

			resp = json.dumps({"code": 0, "data": result}, ensure_ascii=False)
			print(f"[DASHBOARD-API] 返回JSON长度={len(resp)}字节, 前200字符={resp[:200]}", flush=True)
			self.write(resp)

		except Exception as e:
			traceback.print_exc()
			sys.stdout.flush()
			self.write(json.dumps({"code": 1, "msg": str(e), "data": result}, ensure_ascii=False))
