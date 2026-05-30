import traceback
from datetime import datetime, timezone, timedelta
from app.models.db import get_connection

try:
	from apscheduler.schedulers.background import BackgroundScheduler
	from apscheduler.triggers.cron import CronTrigger
	from apscheduler.triggers.date import DateTrigger
	HAS_SCHEDULER = True
except ImportError:
	HAS_SCHEDULER = False

_scheduler = None

BEIJING_TZ = timezone(timedelta(hours=8))

def _utcnow():
	return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _get_scheduler():
	global _scheduler
	if _scheduler is None and HAS_SCHEDULER:
		try:
			_scheduler = BackgroundScheduler(timezone=BEIJING_TZ)
			print("[Scheduler] BackgroundScheduler created (TZ=UTC+8)", flush=True)
		except Exception as e:
			print(f"[Scheduler] TZ creation failed: {e}, using default", flush=True)
			_scheduler = BackgroundScheduler()
	return _scheduler

def execute_crawl_task(schedule_id):
	print(f"[Scheduler] ===== execute_crawl_task START, schedule_id={schedule_id} =====", flush=True)
	try:
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM crawl_schedules WHERE id=?", (schedule_id,)).fetchone()
			if not row:
				print(f"[Scheduler] schedule_id={schedule_id} NOT FOUND in DB", flush=True)
				return
			if not row["is_enabled"]:
				print(f"[Scheduler] schedule_id={schedule_id} is disabled, skip", flush=True)
				return

			from app.models.outlook import OutlookSourceRepository, OutlookCollector, CrawlLogRepository

			source = OutlookSourceRepository.get_source_by_id(row["source_id"])
			if not source:
				print(f"[Scheduler] source_id={row['source_id']} NOT FOUND, disabling task", flush=True)
				conn.execute("UPDATE crawl_schedules SET is_enabled=0 WHERE id=?", (schedule_id,))
				return

			source_name = row["source_name"] or source.get("name", "")
			keyword = row.get("keyword", "")
			pages = row.get("pages", 1)
			per_page = row.get("per_page", 10)

			print(f"[Scheduler] Task: source={source_name} keyword={keyword} pages={pages} per_page={per_page}", flush=True)

			log_id = CrawlLogRepository.create_log(schedule_id, row["source_id"], source_name, keyword)
			print(f"[Scheduler] crawl_log id={log_id} created", flush=True)

			t_start = datetime.now(timezone.utc)
			saved_count = OutlookCollector.collect(
				source=source,
				keyword=keyword,
				pages=pages,
				page_size_step=per_page,
				use_ai_expand=False,
				use_ai_clean=False,
				task_id=schedule_id
			)
			t_elapsed = round((datetime.now(timezone.utc) - t_start).total_seconds(), 1)

			print(f"[Scheduler] ===== DONE: saved={saved_count}, elapsed={t_elapsed}s =====", flush=True)
			CrawlLogRepository.complete_log(log_id, total_count=saved_count, saved_count=saved_count)
			conn.execute("UPDATE crawl_schedules SET last_run=?, is_enabled=0 WHERE id=?", (_utcnow(), schedule_id))
	except Exception as e:
		print(f"[Scheduler] schedule_id={schedule_id} FAILED: {e}", flush=True)
		traceback.print_exc()
		from app.models.outlook import CrawlLogRepository
		try:
			if 'log_id' in dir() and log_id:
				CrawlLogRepository.fail_log(log_id, str(e)[:500])
		except Exception:
			pass
		try:
			with get_connection() as conn:
				conn.execute("UPDATE crawl_schedules SET last_run=?, is_enabled=0 WHERE id=?", (_utcnow(), schedule_id))
		except Exception:
			pass

def load_schedules():
	if not HAS_SCHEDULER:
		print("[Scheduler] apscheduler not installed", flush=True)
		return
	sched = _get_scheduler()
	if not sched:
		print("[Scheduler] scheduler is None", flush=True)
		return

	print("[Scheduler] Removing old crawl jobs...", flush=True)
	for job in list(sched.get_jobs()):
		if job.id.startswith("crawl_"):
			try:
				job.remove()
			except Exception:
				pass

	with get_connection() as conn:
		rows = conn.execute("SELECT * FROM crawl_schedules WHERE is_enabled=1").fetchall()
	print(f"[Scheduler] {len(rows)} enabled schedules", flush=True)

	now_beijing = datetime.now(BEIJING_TZ)

	for row in rows:
		try:
			cron_expr = row["cron_expression"].strip()
			parts = cron_expr.split()
			sch_year = row.get("sch_year", 0) or 0
			job_id = f"crawl_{row['id']}"
			print(f"[Scheduler] #{row['id']}: cron='{cron_expr}' sch_year={sch_year}", flush=True)

			if sch_year > 0 and len(parts) >= 4:
				month = int(parts[3])
				day = int(parts[2])
				hour = int(parts[1])
				minute = int(parts[0])
				run_date = datetime(sch_year, month, day, hour, minute, tzinfo=BEIJING_TZ)

				if run_date <= now_beijing:
					print(f"[Scheduler] #{row['id']}: TIME PASSED ({run_date} <= {now_beijing}), disabling", flush=True)
					with get_connection() as conn:
						conn.execute("UPDATE crawl_schedules SET is_enabled=0, last_run=? WHERE id=?", (_utcnow(), row["id"]))
					continue

				sched.add_job(
					execute_crawl_task,
					DateTrigger(run_date=run_date),
					id=job_id,
					args=[row["id"]],
					replace_existing=True,
					misfire_grace_time=60,
					coalesce=True
				)
				remaining = (run_date - now_beijing).total_seconds()
				print(f"[Scheduler] #{row['id']}: DateTrigger @ {run_date} (in {int(remaining)}s)", flush=True)

			elif len(parts) == 5:
				kwargs = {"minute": parts[0], "hour": parts[1], "day": parts[2], "month": parts[3]}
				if parts[4] != "*":
					kwargs["day_of_week"] = parts[4]
				sched.add_job(
					execute_crawl_task,
					CronTrigger(**kwargs),
					id=job_id,
					args=[row["id"]],
					replace_existing=True,
					misfire_grace_time=3600,
					coalesce=True
				)
				j = sched.get_job(job_id)
				print(f"[Scheduler] #{row['id']}: CronTrigger next_run={j.next_run_time if j else 'N/A'}", flush=True)
			else:
				print(f"[Scheduler] #{row['id']}: cannot parse cron", flush=True)
				continue

		except Exception as e:
			print(f"[Scheduler] #{row['id']}: FAILED to add: {e}", flush=True)
			traceback.print_exc()

def start_scheduler():
	if not HAS_SCHEDULER:
		print("[Scheduler] apscheduler not installed", flush=True)
		return
	load_schedules()
	sched = _get_scheduler()
	if sched and not sched.running:
		print("[Scheduler] Starting scheduler...", flush=True)
		sched.start()
		print(f"[Scheduler] Started OK, {len(sched.get_jobs())} jobs", flush=True)
		# 启动工作流引擎定时检查
		_check_workflow_engine()
	elif sched:
		print(f"[Scheduler] already running, {len(sched.get_jobs())} jobs", flush=True)
	else:
		print("[Scheduler] no scheduler to start", flush=True)

def _check_workflow_engine():
	"""每分钟检查一次定时工作流"""
	try:
		from apscheduler.triggers.interval import IntervalTrigger
		sched = _get_scheduler()
		if sched and not sched.get_job('workflow_engine_check'):
			sched.add_job(
				_run_workflow_engine,
				IntervalTrigger(minutes=1),
				id='workflow_engine_check',
				replace_existing=True,
				coalesce=True
			)
			print("[Scheduler] Workflow engine check added (every 1 min)", flush=True)
	except Exception as e:
		print(f"[Scheduler] workflow engine setup error: {e}", flush=True)

def _run_workflow_engine():
	try:
		from app.controllers.admin.workflow import AdminWorkflowEngineHandler
		AdminWorkflowEngineHandler.check_and_run()
	except Exception as e:
		print(f"[WorkflowEngine] check error: {e}", flush=True)

def reload_schedules():
	print("[Scheduler] reload_schedules called", flush=True)
	load_schedules()
	sched = _get_scheduler()
	if sched and not sched.running:
		try:
			sched.start()
			print("[Scheduler] reload: started", flush=True)
		except Exception as e:
			print(f"[Scheduler] reload: start FAILED: {e}", flush=True)
			traceback.print_exc()
