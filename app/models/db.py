# 数据库链接与建表
import os
import json
import sqlite3
def _project_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir,os.pardir))
DB_PATH = os.path.join(_project_root(),"database","app.db")

def get_connection():
	os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn

#创建表的方法
def init_db():
	with get_connection() as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users(
				id integer PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				role TEXT NOT NULL DEFAULT 'user',
				status INTEGER NOT NULL DEFAULT 1,
				can_login_admin INTEGER NOT NULL DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		# 功能模块表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS functions(
				id integer PRIMARY KEY AUTOINCREMENT,
				parent_id INTEGER NOT NULL DEFAULT 0,
				name TEXT NOT NULL,
				code TEXT NOT NULL UNIQUE,
				icon TEXT NOT NULL DEFAULT '',
				url TEXT NOT NULL DEFAULT '',
				sort_order INTEGER NOT NULL DEFAULT 0,
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		# 角色表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS roles(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				description TEXT NOT NULL DEFAULT '',
				is_system INTEGER NOT NULL DEFAULT 0,
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		# 角色-功能权限映射表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS role_functions(
				id integer PRIMARY KEY AUTOINCREMENT,
				role_id INTEGER NOT NULL,
				function_id INTEGER NOT NULL,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				UNIQUE(role_id, function_id)
			)
			"""
		)
		# 创建 outlook_sources 表（瞭望数据源配置）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outlook_sources'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE outlook_sources(
					id integer PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL,
					code TEXT NOT NULL UNIQUE,
					entry_url TEXT NOT NULL,
					method TEXT NOT NULL DEFAULT 'GET',
					request_headers TEXT,
					body_template TEXT,
					parser_type TEXT NOT NULL DEFAULT 'html',
					html_selector TEXT,
					title_selector TEXT,
					url_selector TEXT,
					content_selector TEXT,
					date_selector TEXT,
					author_selector TEXT,
					page_size_step INTEGER NOT NULL DEFAULT 10,
					page_start INTEGER NOT NULL DEFAULT 0,
					ai_expand_keyword INTEGER NOT NULL DEFAULT 0,
					ai_expand_prompt TEXT,
					ai_clean_data INTEGER NOT NULL DEFAULT 0,
					ai_clean_prompt TEXT,
					status INTEGER NOT NULL DEFAULT 1,
					description TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 outlook_data 表（瞭望采集到的数据）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outlook_data'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE outlook_data(
					id integer PRIMARY KEY AUTOINCREMENT,
					source_id INTEGER NOT NULL,
					source_name TEXT,
					source_keyword TEXT,
					title TEXT NOT NULL,
					url TEXT,
					content TEXT,
					author TEXT,
					publish_date TEXT,
					raw_html TEXT,
					ai_processed INTEGER NOT NULL DEFAULT 0,
					ai_deep_status INTEGER NOT NULL DEFAULT 0,
					task_id INTEGER NOT NULL DEFAULT 0,
					collect_status TEXT NOT NULL DEFAULT 'success',
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 升级 outlook_data 表字段
		cursor = conn.execute("PRAGMA table_info(outlook_data)")
		columns = [row[1] for row in cursor.fetchall()]
		if len(columns) > 0:
			if 'ai_deep_status' not in columns:
				conn.execute("ALTER TABLE outlook_data ADD COLUMN ai_deep_status INTEGER NOT NULL DEFAULT 0")

		# 创建 outlook_data_detail 表（AI深度采集结果）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outlook_data_detail'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE outlook_data_detail(
					id integer PRIMARY KEY AUTOINCREMENT,
					data_id INTEGER NOT NULL,
					task_id INTEGER NOT NULL DEFAULT 0,
					source_id INTEGER NOT NULL,
					source_name TEXT,
					title TEXT,
					url TEXT,
					raw_content TEXT,
					deep_content TEXT,
					summary TEXT,
					key_points TEXT,
					model_used TEXT,
					status TEXT NOT NULL DEFAULT 'pending',
					error_msg TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)
		else:
			# 检查是否有raw_content字段
			cursor2 = conn.execute("PRAGMA table_info(outlook_data_detail)")
			columns = [row[1] for row in cursor2.fetchall()]
			if 'raw_content' not in columns:
				conn.execute("ALTER TABLE outlook_data_detail ADD COLUMN raw_content TEXT")

		# 创建 outlook_tasks 表（瞭望采集任务）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outlook_tasks'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE outlook_tasks(
					id integer PRIMARY KEY AUTOINCREMENT,
					keyword TEXT NOT NULL,
					source_ids TEXT NOT NULL DEFAULT '',
					source_names TEXT NOT NULL DEFAULT '',
					pages INTEGER NOT NULL DEFAULT 1,
					page_size_step INTEGER NOT NULL DEFAULT 10,
					ai_expand INTEGER NOT NULL DEFAULT 0,
					ai_clean INTEGER NOT NULL DEFAULT 0,
					total_count INTEGER NOT NULL DEFAULT 0,
					status TEXT NOT NULL DEFAULT 'completed',
					error_msg TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 outlook_sentiment_cache 表（舆情分析结果缓存）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outlook_sentiment_cache'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE outlook_sentiment_cache(
					id integer PRIMARY KEY AUTOINCREMENT,
					result_json TEXT NOT NULL,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 api_interfaces 表（第三方接口管理）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_interfaces'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE api_interfaces(
					id integer PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL,
					code TEXT NOT NULL UNIQUE,
					api_url TEXT NOT NULL,
					method TEXT NOT NULL DEFAULT 'GET',
					response_format TEXT NOT NULL DEFAULT 'JSON',
					request_example TEXT,
					params_schema TEXT,
					headers TEXT,
					description TEXT,
					qps_limit TEXT,
					status INTEGER NOT NULL DEFAULT 1,
					total_calls INTEGER NOT NULL DEFAULT 0,
					last_called_at TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)
		_init_default_api_interfaces(conn)

		# 初始化默认瞭望数据源
		cursor = conn.execute("SELECT COUNT(*) as cnt FROM outlook_sources").fetchone()
		if cursor["cnt"] == 0:
			default_headers = json.dumps({
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
			"Accept-Encoding": "gzip, deflate, br, zstd",
			"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
			"Connection": "keep-alive",
			"Cookie": "BAIDUID=7D040A0375AC5C5FC9A8629972B20BBB:FG=1; BAIDUID_BFESS=7D040A0375AC5C5FC9A8629972B20BBB:FG=1; BDUSS=RrZ0d0OWNGVXp1fmkxbElCc2JpWnhXMTg3YTVpeDkwQlFvS3lmOFNGT3VYUzlxSVFBQUFBJCQAAAAAAQAAAAEAAAALpsEiAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAK7QB2qu0AdqTE; BDUSS_BFESS=RrZ0d0OWNGVXp1fmkxbElCc2JpWnhXMTg3YTVpeDkwQlFvS3lmOFNGT3VYUzlxSVFBQUFBJCQAAAAAAQAAAAEAAAALpsEiAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAK7QB2qu0AdqTE; PSTM=1779582680; BDRCVFR[xxJIjd-9mMY]=9xWipS8B-FspA7EnHc1QhPEUf; H_PS_PSSID=63142_67861_68166_68464_69205_69296_69592_69764_69798_69782_69846_69908_69949_69962_70005_70007_70048_70090_70117_70131_70156_70169_70222_70252_70199_70196_70288_70285_68736_70321_70142_69921_70358_70416_70441_70477_70476_70472; BD_UPN=12314753; BIDUPSID=AF970139E2195A6F4B11A9C960F71109; BA_HECTOR=8l2g818g0g802l25ag81a50l01800h1l14hmp29; ZFY=LHvroeutiKiiTbvzk7W:Boj9l8a0ANl1powqxNeAgN3Y:C; BD_CK_SAM=1; delPer=0; BDORZ=FFFB88E999055A3F8A630C64834BD6D0; BDSFRCVID=vNPOJeC62ZWuHpc8L4pUU99sWCuEGM7TH6aorVxuAZ4sKOFklb8XEG0n-U8g0KAMvsHJogKKXgOTH9uF_2uxOjjg8UtVJeC6EG0Ptf8g0U5; BDSFRCVID_BFESS=vNPOJeC62ZWuHpc8L4pUU99sWCuEGM7TH6aorVxuAZ4sKOFklb8XEG0n-U8g0KAMvsHJogKKXgOTH9uF_2uxOjjg8UtVJeC6EG0Ptf8g0U5; H_BDCLCKID_SF=JnutoI-KfI_3DJ7g-tP_-PJM54TTWMT-0bFHhf3aWPJjbh4mKholejFy3Pbt0xbuJan7_JjO-fQWfqjLjbbvXUKfhMKOXUQxtI_L-CnjtpvN8tQRyM6obUPUWMJ9LUk8bmcdot5yBbc8eIna5hjkbfJBQttjQn3hfIkj-CKLK-oj-D8Cj6K53j; H_BDCLCKID_SF_BFESS=JnutoI-KfI_3DJ7g-tP_-PJM54TTWMT-0bFHhf3aWPJjbh4mKholejFy3Pbt0xbuJan7_JjO-fQWfqjLjbbvXUKfhMKOXUQxtI_L-CnjtpvN8tQRyM6obUPUWMJ9LUk8bmcdot5yBbc8eIna5hjkbfJBQttjQn3hfIkj-CKLK-oj-D8Cj6K53j; COOKIE_SESSION=21233444_3_8_9_2_25_0_1_7_6_1_11_39_21233481_0_6_1758349308_1779582707_1779582701%7C9%2321233478_14_1779582701%7C4; H_WISE_SIDS=63142_67861_68166_68464_69205_69296_69592_69764_69798_69782_69846_69908_69949_69962_70005_70007_70048_70090_70117_70131_70156_70169_70222_70252_70199_70196_70288_70285_68736_70321_70142_69921_70358_70416_70441_70477_70476_70472; PSINO=7; H_PS_645EC=da77%2FWLTn2u87bDDJeoGs%2B91y%2BfMM%2Bj3XWoq8TPM6LWYOyo3Jz07EmaAWiXxutZoBp4QExhbLuOv; BDSVRTM=420",
			"Host": "www.baidu.com",
			"Referer": "https://news.baidu.com/",
			"Sec-Fetch-Dest": "document",
			"Sec-Fetch-Mode": "navigate",
			"Sec-Fetch-Site": "same-site",
			"Sec-Fetch-User": "?1",
			"Upgrade-Insecure-Requests": "1",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
		})
			conn.execute(
				"""INSERT INTO outlook_sources(name,code,entry_url,method,request_headers,parser_type,
				html_selector,title_selector,url_selector,content_selector,date_selector,author_selector,
				page_size_step,page_start,ai_expand_keyword,ai_clean_data,status,description)
				VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
			('百度新闻', 'baidu_news', 'https://www.baidu.com/s?tn=news&word={keyword}&pn={page}',
				'GET', default_headers, 'html',
				'//div[contains(@class,"result")]', './/h3', './/h3/a', './/div[contains(@class,"content-right")]//span', './/span[contains(@class,"c-color-gray2")]', './/p[contains(@class,"author-text")]',
				10, 0, 1,
				'请对采集到的新闻标题和内容进行AI清洗，去除无关信息，提取核心要点，并以JSON格式返回：[{"title":"标题","content":"摘要","author":"作者","date":"日期"}]',
				1, '百度新闻搜索引擎采集源')
			)
			# 更多采集源
			_more_sources = [
				('搜狗新闻', 'sogou_news', 'https://news.sogou.com/news?query={keyword}&page={page}',
				'GET', 'html',
				'//div[contains(@class,"vrwrap")]',
				'.//h3', './/h3/a', '', '', '',
				10, 1, 0, '', 0, '', 1, '搜狗新闻搜索引擎采集源'),
				('360新闻', 'so_news', 'https://www.so.com/s?q={keyword}&pn={page}',
				'GET', 'html',
				'//li[contains(@class,"res-list")]',
				'.//h3', './/a', './/p[contains(@class,"summary")]', './/p[contains(@class,"g-linkinfo")]', '',
				10, 1, 0, '', 0, '', 1, '360搜索引擎采集源（https://www.so.com）'),
			]
			for ms in _more_sources:
				conn.execute(
					"""INSERT INTO outlook_sources(
					name,code,entry_url,method,parser_type,
					html_selector,title_selector,url_selector,content_selector,date_selector,author_selector,
					page_size_step,page_start,ai_expand_keyword,ai_expand_prompt,ai_clean_data,ai_clean_prompt,
					status,description)
					VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
					ms
				)

		# 初始化默认用户
		cursor = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
		if cursor["cnt"] == 0:
			from app.models.user import _hash_password
			import secrets
			salt = secrets.token_bytes(16)
			password_hash = _hash_password("admin888", salt)
			conn.execute(
				"INSERT INTO users(username,password_hash,salt,role,status,can_login_admin) VALUES(?,?,?,?,?,?)",
				("admin", password_hash, salt.hex(), "admin", 1, 1)
			)
			# 创建测试用户 test1 和 test2
			salt1 = secrets.token_bytes(16)
			password_hash1 = _hash_password("test1234", salt1)
			conn.execute(
				"INSERT INTO users(username,password_hash,salt,role,status,can_login_admin) VALUES(?,?,?,?,?,?)",
				("test1", password_hash1, salt1.hex(), "user", 1, 0)
			)
			salt2 = secrets.token_bytes(16)
			password_hash2 = _hash_password("test1234", salt2)
			conn.execute(
				"INSERT INTO users(username,password_hash,salt,role,status,can_login_admin) VALUES(?,?,?,?,?,?)",
				("test2", password_hash2, salt2.hex(), "user", 1, 0)
			)

		# 预置 IM 测试好友数据（在 IM 表创建后执行）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_friends'")
		if cursor.fetchone():
			# 确保测试用户存在
			from app.models.user import _hash_password
			import secrets

			def ensure_user(username, password="test1234"):
				row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
				if not row:
					salt = secrets.token_bytes(16)
					pw_hash = _hash_password(password, salt)
					conn.execute(
						"INSERT INTO users(username,password_hash,salt,role,status,can_login_admin) VALUES(?,?,?,?,?,?)",
						(username, pw_hash, salt.hex(), "user", 1, 0)
					)
					row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
				return row["id"]

			aid = ensure_user("admin", "admin123")
			t1id = ensure_user("test1")
			t2id = ensure_user("test2")
			zhangsan_id = ensure_user("张三")
			zhangsan1_id = ensure_user("张三1")
			zhangsan2_id = ensure_user("张三2")
			lisi_id = ensure_user("李四")
			wangwu_id = ensure_user("王五")

			# 检查是否已有好友数据
			fc = conn.execute("SELECT COUNT(*) as cnt FROM im_friends").fetchone()
			if fc["cnt"] == 0:
				# admin ↔ test1 互为好友
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (aid, t1id))
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (t1id, aid))
				# admin ↔ test2 互为好友
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (aid, t2id))
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (t2id, aid))
				# admin ↔ 张三 互为好友
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (aid, zhangsan_id))
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (zhangsan_id, aid))
				# test1 ↔ 张三1 互为好友
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (t1id, zhangsan1_id))
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (zhangsan1_id, t1id))
				# test1 ↔ 张三2 互为好友
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (t1id, zhangsan2_id))
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (zhangsan2_id, t1id))
				# test2 ↔ 李四 互为好友
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (t2id, lisi_id))
				conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (lisi_id, t2id))

			# 预置好友申请 mock 数据
			frc = conn.execute("SELECT COUNT(*) as cnt FROM im_friend_requests").fetchone()
			if frc["cnt"] == 0:
				# admin 收到 test1 的申请（待处理）
				conn.execute("INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
					(t1id, aid, "你好，我是test1，想加你为好友", "pending"))
				# admin 收到 李四 的申请（待处理）
				conn.execute("INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
					(lisi_id, aid, "你好，我是李四", "pending"))
				# admin 收到 王五 的申请（已同意）
				conn.execute("INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
					(wangwu_id, aid, "你好，我是王五", "accepted"))
				# admin 发出的申请给 张三1（待处理）
				conn.execute("INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
					(aid, zhangsan1_id, "你好，我想加你为好友", "pending"))
				# admin 发出的申请给 张三2（已拒绝）
				conn.execute("INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
					(aid, zhangsan2_id, "你好，认识一下", "rejected"))
				# test1 收到 张三 的申请（已同意）
				conn.execute("INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
					(zhangsan_id, t1id, "你好，我是张三", "accepted"))

		# 创建 crawl_logs 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_logs'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE crawl_logs(
					id integer PRIMARY KEY AUTOINCREMENT,
					task_id INTEGER NOT NULL DEFAULT 0,
					source_id INTEGER NOT NULL,
					source_name TEXT,
					keyword TEXT,
					start_time TEXT,
					end_time TEXT,
					total_count INTEGER NOT NULL DEFAULT 0,
					saved_count INTEGER NOT NULL DEFAULT 0,
					status TEXT NOT NULL DEFAULT 'running',
					error_msg TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 crawl_schedules 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_schedules'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE crawl_schedules(
					id integer PRIMARY KEY AUTOINCREMENT,
					source_id INTEGER NOT NULL,
					source_name TEXT,
					keyword TEXT,
					cron_expression TEXT NOT NULL,
					sch_year INTEGER NOT NULL DEFAULT 0,
					pages INTEGER NOT NULL DEFAULT 1,
					per_page INTEGER NOT NULL DEFAULT 10,
					is_enabled INTEGER NOT NULL DEFAULT 1,
					last_run TEXT,
					next_run TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# crawl_schedules 表新增 sch_year 字段
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_schedules'")
		if cursor.fetchone():
			cursor2 = conn.execute("PRAGMA table_info(crawl_schedules)")
			columns = [row["name"] for row in cursor2.fetchall()]
			if "sch_year" not in columns:
				conn.execute("ALTER TABLE crawl_schedules ADD COLUMN sch_year INTEGER NOT NULL DEFAULT 0")

		# crawl_schedules 表新增 schedule_type 字段
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_schedules'")
		if cursor.fetchone():
			cursor2 = conn.execute("PRAGMA table_info(crawl_schedules)")
			columns = [row["name"] for row in cursor2.fetchall()]
			if "schedule_type" not in columns:
				conn.execute("ALTER TABLE crawl_schedules ADD COLUMN schedule_type TEXT NOT NULL DEFAULT 'once'")

		# 创建 assistants 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assistants'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE assistants(
					id integer PRIMARY KEY AUTOINCREMENT,
					assistant_name TEXT NOT NULL,
					assistant_code TEXT NOT NULL UNIQUE,
					icon TEXT NOT NULL DEFAULT 'layui-icon-user',
					prompt_template TEXT,
					model_id INTEGER,
					sort_order INTEGER NOT NULL DEFAULT 0,
					is_enabled INTEGER NOT NULL DEFAULT 1,
					api_key TEXT,
					api_url TEXT,
					description TEXT,
					category TEXT NOT NULL DEFAULT 'AI',
					api_interface_id INTEGER,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)
		else:
			cursor2 = conn.execute("PRAGMA table_info(assistants)")
			cols = [r[1] for r in cursor2.fetchall()]
			if 'category' not in cols:
				conn.execute("ALTER TABLE assistants ADD COLUMN category TEXT NOT NULL DEFAULT 'AI'")
			if 'api_interface_id' not in cols:
				conn.execute("ALTER TABLE assistants ADD COLUMN api_interface_id INTEGER")

		# 创建 chat_history 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE chat_history(
					id integer PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL,
					assistant_id INTEGER,
					model_id INTEGER,
					role TEXT NOT NULL,
					content TEXT NOT NULL,
					prompt_tokens INTEGER NOT NULL DEFAULT 0,
					completion_tokens INTEGER NOT NULL DEFAULT 0,
					total_tokens INTEGER NOT NULL DEFAULT 0,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 初始化默认数据
		_init_default_data(conn)

		# 初始化默认数字员工
		asst_cnt = conn.execute("SELECT COUNT(*) as cnt FROM assistants").fetchone()["cnt"]
		if asst_cnt == 0:
			weather_id = conn.execute("SELECT id FROM api_interfaces WHERE code='weather_tian'").fetchone()
			music_id = conn.execute("SELECT id FROM api_interfaces WHERE code='music_qq_vip'").fetchone()
			default_assistants = [
				("川小农", "chuangxiaonong", "layui-icon-user",
					"你是「川小农」，专注农业智能服务的AI助手。提供农业政策解读、种植技术指导、农产品市场分析等服务。请用专业且易懂的中文回答。",
					None, 1, 1, "", "", "专注农业领域的智能助手", "AI", None),
				("通用AI助手", "general_ai", "layui-icon-user",
					"你是一个智能对话助手，能够回答各类问题，提供建议和帮助。请用友好、专业的方式回应用户。",
					None, 2, 1, "", "", "通用AI对话助手", "AI", None),
				("数据分析师", "data_analyst", "layui-icon-align-left",
					"你是一个专业的数据分析师。擅长解读数据、生成报表、发现趋势并提出数据驱动的建议。回复时请条理清晰，使用数据和事实支撑观点。",
					None, 3, 1, "", "", "数据分析与洞察专家", "AI", None),
				("翻译助手", "translator", "fas fa-language",
					"你是一个多语言翻译专家。能够准确翻译中英文，并保持原文的语气和风格。对于专业术语，你会提供准确的翻译和解释。",
					None, 4, 1, "", "", "多语言翻译专家", "AI", None),
				("代码助手", "code_helper", "fas fa-code",
					"你是一个编程助手，擅长编写、调试和优化代码。请提供清晰、可运行的代码示例，并解释关键逻辑。",
					None, 5, 1, "", "", "编程与代码调试助手", "AI", None),
				("天气查询", "weather_query", "fas fa-cloud-sun",
					"天气查询助手，可查询全国城市的实时天气、三日预报、空气质量等信息。",
					None, 6, 1, "", "", "三日天气查询服务", "API", weather_id["id"] if weather_id else None),
				("音乐助手", "music_helper", "fas fa-music",
					"QQ音乐VIP搜索助手，可搜索歌手、歌曲信息，获取高品质音乐资源。",
					None, 7, 1, "", "", "QQ音乐VIP歌曲搜索", "API", music_id["id"] if music_id else None),
				("毒鸡汤助手", "poison_chicken_soup", "fas fa-skull",
					"你是毒鸡汤助手，专长是用尖锐而幽默的方式讲出扎心的大实话。\n"
					"请根据用户的输入，随机回复一条毒鸡汤语录。\n"
					"毒鸡汤应当：\n"
					"1. 简短有力，一两句话即可\n"
					"2. 带有黑色幽默或反讽色彩\n"
					"3. 既要扎心又要让人会心一笑\n"
					"4. 可以根据用户输入内容进行针对性回复\n"
					"5. 不要过于恶毒或人身攻击，保持幽默底线\n\n"
					"示例风格：\n"
					"- \u201c努力不一定成功，但不努力一定很舒服。\u201d\n"
					"- \u201c你以为你是主角，其实你连NPC都不如。\u201d\n"
					"- \u201c加油，你是最胖的！\u201d",
					None, 8, 1, "", "", "随机回复毒鸡汤语句，让人清醒的扎心语录", "AI", None),
			]
			for a in default_assistants:
				conn.execute(
					"INSERT INTO assistants(assistant_name,assistant_code,icon,prompt_template,model_id,sort_order,is_enabled,api_key,api_url,description,category,api_interface_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
					a
				)
		# ==================== 多IM服务器集群表 ====================

		# 创建 im_server_nodes 表（服务注册表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_server_nodes'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_server_nodes(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					node_id TEXT NOT NULL UNIQUE,
					host TEXT NOT NULL,
					public_port INTEGER NOT NULL,
					internal_port INTEGER NOT NULL,
					pid INTEGER NOT NULL DEFAULT 0,
					status TEXT NOT NULL DEFAULT 'starting',
					load_score REAL NOT NULL DEFAULT 0,
					connection_count INTEGER NOT NULL DEFAULT 0,
					max_connections INTEGER NOT NULL DEFAULT 200,
					started_at TEXT,
					last_heartbeat TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 im_user_node_map 表（用户-节点映射表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_user_node_map'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_user_node_map(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL UNIQUE,
					node_id TEXT NOT NULL,
					assigned_at TEXT NOT NULL DEFAULT(datetime('now')),
					last_active_at TEXT,
					is_active INTEGER NOT NULL DEFAULT 1
				)
				"""
			)

		# 创建 im_message_delivery 表（消息投递确认表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_message_delivery'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_message_delivery(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					msg_id INTEGER NOT NULL,
					conv_id INTEGER NOT NULL,
					sender_id INTEGER NOT NULL,
					target_user_id INTEGER NOT NULL,
					target_node_id TEXT NOT NULL,
					status TEXT NOT NULL DEFAULT 'pending',
					fail_reason TEXT,
					retry_count INTEGER NOT NULL DEFAULT 0,
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					delivered_at TEXT
				)
				"""
			)

		conn.commit()

def _init_default_api_interfaces(conn):
	"""初始化默认第三方 API 接口"""
	cursor = conn.execute("SELECT COUNT(*) as cnt FROM api_interfaces").fetchone()
	if cursor["cnt"] > 0:
		return
	defaults = [
		(
			'QQ音乐VIP', 'music_qq_vip',
			'https://api.52vmy.cn/api/music/qq/vip',
			'GET', 'TEXT',
			'https://api.52vmy.cn/api/music/qq/vip?msg=周杰伦',
			'[{"name":"msg","label":"歌手/歌曲","example":"周杰伦","required":true}]',
			'', 'QQ音乐VIP歌曲搜索接口', '', 1
		),
		(
			'天气查询', 'weather_tian',
			'https://api.52vmy.cn/api/query/tian',
			'GET', 'JSON',
			'https://api.52vmy.cn/api/query/tian?city=北京市',
			'[{"name":"city","label":"城市","example":"北京市","required":true}]',
			'', '三日天气查询API', '每2秒最多4次，携带Token可无视限制', 1
		),
	]
	for item in defaults:
		conn.execute(
			"""INSERT INTO api_interfaces(
			name,code,api_url,method,response_format,request_example,
			params_schema,headers,description,qps_limit,status
			) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
			item
		)

def _init_default_data(conn):
	"""初始化默认的功能、角色和权限数据"""
	# 检查是否已有功能数据
	count = conn.execute("SELECT COUNT(*) as cnt FROM functions").fetchone()["cnt"]
	if count > 0:
		return

	# 插入默认功能模块（二级结构）
	functions = [
		# 一级菜单(parent_id=0)
		(0, '基础管理', 'base', 'layui-icon-set', '', 1, 1),
		(0, '核心业务', 'business', 'layui-icon-engine', '', 2, 1),
		(0, '瞭望采集', 'data', 'layui-icon-read', '', 3, 1),
		(0, '数智大屏', 'biz_dashboard', 'layui-icon-chart', '', 4, 1),
		(0, '系统', 'system', 'layui-icon-component', '', 5, 1),
		# 二级菜单
		(1, '系统首页', 'base_index', 'layui-icon-home', '/admin', 1, 1),
		(1, '用户管理', 'base_users', 'layui-icon-username', '/admin/users', 2, 1),
		(1, '角色管理', 'base_roles', 'layui-icon-group', '/admin/roles', 3, 1),
		(1, '功能管理', 'base_functions', 'layui-icon-menu-fill', '/admin/functions', 4, 1),
		(1, '权限管理', 'base_permissions', 'layui-icon-auz', '/admin/permissions', 5, 1),
		(2, '模型引擎', 'biz_models', 'layui-icon-engine', '/admin/models', 1, 1),
		(2, '数字员工', 'biz_employees', 'layui-icon-user', '/admin/agent', 2, 1),
		(3, '瞭望采集', 'biz_outlook', 'layui-icon-search', '/admin/outlook', 1, 1),
		(3, '数据仓库', 'data_warehouse', 'layui-icon-table', '/admin/warehouse', 2, 1),
		(3, '接口管理', 'data_api', 'layui-icon-link', '/admin/api', 3, 1),
		(3, '定时采集', 'outlook_schedule', 'layui-icon-log', '/admin/outlook/schedule', 4, 1),
		(3, '采集日志', 'outlook_log', 'layui-icon-file', '/admin/outlook/log', 5, 1),
		(4, '数智大屏', 'biz_dashboard_home', 'layui-icon-home', '/dashboard', 1, 1),
		(5, '系统设置', 'sys_settings', 'layui-icon-set', '/admin/settings', 1, 1),
	]
	for f in functions:
		conn.execute(
			"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
			f
		)

	# 插入默认角色
	roles = [
		('超级管理员', 'admin', '系统最高权限，不可修改和删除', 1, 1),
		('管理员', 'manager', '系统管理员权限', 0, 1),
		('普通用户', 'user', '普通用户权限', 0, 1),
	]
	for r in roles:
		conn.execute(
			"INSERT INTO roles(name,code,description,is_system,status) VALUES(?,?,?,?,?)",
			r
		)

	# 为超级管理员分配所有权限
	cursor = conn.execute("SELECT id FROM functions")
	func_ids = [row["id"] for row in cursor.fetchall()]
	cursor = conn.execute("SELECT id FROM roles WHERE code='admin'")
	super_admin_id = cursor.fetchone()["id"]
	for fid in func_ids:
		conn.execute(
			"INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)",
			(super_admin_id, fid)
		)

def upgrade_db():
	with get_connection() as conn:
		# 升级 users 表
		cursor = conn.execute("PRAGMA table_info(users)")
		columns = [row[1] for row in cursor.fetchall()]
		if 'role' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
		if 'status' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN status INTEGER NOT NULL DEFAULT 1")
		if 'create_at' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN create_at TEXT NOT NULL DEFAULT(datetime('now'))")
		if 'can_login_admin' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN can_login_admin INTEGER NOT NULL DEFAULT 0")
			conn.execute("UPDATE users SET can_login_admin=1 WHERE username='admin'")

		# 创建 outlook_tasks 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outlook_tasks'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE outlook_tasks(
					id integer PRIMARY KEY AUTOINCREMENT,
					keyword TEXT NOT NULL,
					source_ids TEXT NOT NULL DEFAULT '',
					source_names TEXT NOT NULL DEFAULT '',
					pages INTEGER NOT NULL DEFAULT 1,
					page_size_step INTEGER NOT NULL DEFAULT 10,
					ai_expand INTEGER NOT NULL DEFAULT 0,
					ai_clean INTEGER NOT NULL DEFAULT 0,
					total_count INTEGER NOT NULL DEFAULT 0,
					status TEXT NOT NULL DEFAULT 'completed',
					error_msg TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# outlook_data 添加 task_id 和 source_keyword 字段
		cursor = conn.execute("PRAGMA table_info(outlook_data)")
		data_cols = [row[1] for row in cursor.fetchall()]
		if len(data_cols) > 0:
			if 'task_id' not in data_cols:
				conn.execute("ALTER TABLE outlook_data ADD COLUMN task_id INTEGER NOT NULL DEFAULT 0")
			if 'source_keyword' not in data_cols:
				conn.execute("ALTER TABLE outlook_data ADD COLUMN source_keyword TEXT NOT NULL DEFAULT ''")

		# 一次性修复：修复被错误累加8小时的时间数据（仅执行一次）
		# 检测是否已经执行过修复（通过检查是否有时间大于当前时间的记录）
		cursor = conn.execute("SELECT COUNT(*) as cnt FROM outlook_tasks WHERE create_at > datetime('now','+1 hour')").fetchone()
		if cursor["cnt"] > 0:
			# 有异常数据，减去8小时
			conn.execute("UPDATE outlook_tasks SET create_at = datetime(create_at, '-8 hours') WHERE create_at > datetime('now','+1 hour')")
			conn.execute("UPDATE outlook_data SET create_at = datetime(create_at, '-8 hours') WHERE create_at > datetime('now','+1 hour')")

		# 创建 functions 表（如果不存在）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='functions'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE functions(
					id integer PRIMARY KEY AUTOINCREMENT,
					parent_id INTEGER NOT NULL DEFAULT 0,
					name TEXT NOT NULL,
					code TEXT NOT NULL UNIQUE,
					icon TEXT NOT NULL DEFAULT '',
					url TEXT NOT NULL DEFAULT '',
					sort_order INTEGER NOT NULL DEFAULT 0,
					status INTEGER NOT NULL DEFAULT 1,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 roles 表（如果不存在）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roles'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE roles(
					id integer PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL UNIQUE,
					code TEXT NOT NULL UNIQUE,
					description TEXT NOT NULL DEFAULT '',
					is_system INTEGER NOT NULL DEFAULT 0,
					status INTEGER NOT NULL DEFAULT 1,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 role_functions 表（如果不存在）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_functions'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE role_functions(
					id integer PRIMARY KEY AUTOINCREMENT,
					role_id INTEGER NOT NULL,
					function_id INTEGER NOT NULL,
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					UNIQUE(role_id, function_id)
				)
				"""
			)

		# 创建 models 表（如果不存在）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='models'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE models(
					id integer PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL,
					code TEXT NOT NULL UNIQUE,
					api_url TEXT NOT NULL DEFAULT 'https://aigc-api.aitoolcore.com/api/v1/chat/completions',
					api_key TEXT NOT NULL DEFAULT '',
					status INTEGER NOT NULL DEFAULT 1,
					is_system_default INTEGER NOT NULL DEFAULT 0,
					total_requests INTEGER NOT NULL DEFAULT 0,
					total_tokens INTEGER NOT NULL DEFAULT 0,
					prompt_tokens INTEGER NOT NULL DEFAULT 0,
					completion_tokens INTEGER NOT NULL DEFAULT 0,
					last_used_at TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 升级 models 表字段
		cursor = conn.execute("PRAGMA table_info(models)")
		columns = [row[1] for row in cursor.fetchall()]
		if len(columns) > 0:
			# 添加缺少的字段
			if 'api_url' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN api_url TEXT NOT NULL DEFAULT 'https://aigc-api.aitoolcore.com/api/v1/chat/completions'")
			if 'api_key' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN api_key TEXT NOT NULL DEFAULT ''")
			if 'is_system_default' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN is_system_default INTEGER NOT NULL DEFAULT 0")
			if 'total_requests' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN total_requests INTEGER NOT NULL DEFAULT 0")
			if 'total_tokens' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN total_tokens INTEGER NOT NULL DEFAULT 0")
			if 'prompt_tokens' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN prompt_tokens INTEGER NOT NULL DEFAULT 0")
			if 'completion_tokens' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN completion_tokens INTEGER NOT NULL DEFAULT 0")
			if 'last_used_at' not in columns:
				conn.execute("ALTER TABLE models ADD COLUMN last_used_at TEXT")

		# 检查是否需要初始化模型数据
		cursor = conn.execute("SELECT COUNT(*) as cnt FROM models").fetchone()
		if cursor["cnt"] == 0:
			try:
				from config.models_config import MODELS_CONFIG
				for mc in MODELS_CONFIG:
					conn.execute(
						"INSERT INTO models(name,code,api_url,api_key,status,is_system_default) VALUES(?,?,?,?,?,?)",
						(mc['name'], mc['code'], mc['api_url'], mc['api_key'], mc['status'], mc['is_system_default'])
					)
			except ImportError:
				# 如果配置文件不存在，使用默认配置
				conn.execute(
					"INSERT INTO models(name,code,api_url,api_key,status,is_system_default) VALUES(?,?,?,?,?,?)",
					('DeepSeek V3', 'deepseek-v3', 'https://aigc-api.aitoolcore.com/api/v1/chat/completions', 'sk-aigc-c0725a1b8a1b205154867945a3c667ce9d232fa7', 1, 1)
				)

		# 重组菜单：瞭望采集（一级）下含瞭望采集、数据仓库（二级）
		data_row = conn.execute(
			"SELECT id FROM functions WHERE parent_id=0 AND code='data'"
		).fetchone()
		if data_row:
			data_id = data_row["id"]
			conn.execute(
				"UPDATE functions SET name='瞭望采集', icon='layui-icon-read' WHERE id=?",
				(data_id,)
			)
			outlook_row = conn.execute(
				"SELECT id FROM functions WHERE code='biz_outlook'"
			).fetchone()
			if outlook_row:
				conn.execute(
					"UPDATE functions SET name='瞭望采集', parent_id=?, sort_order=1, icon='layui-icon-search', url='/admin/outlook' WHERE id=?",
					(data_id, outlook_row["id"])
				)
			else:
				conn.execute(
					"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
					(data_id, "瞭望采集", "biz_outlook", "layui-icon-search", "/admin/outlook", 1, 1)
				)
				new_outlook_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
				admin_role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
				if admin_role:
					conn.execute(
						"INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)",
						(admin_role["id"], new_outlook_id)
					)
			conn.execute(
				"UPDATE functions SET parent_id=?, sort_order=2 WHERE code='data_warehouse'",
				(data_id,)
			)
			conn.execute(
				"UPDATE functions SET parent_id=?, sort_order=3 WHERE code='data_api'",
				(data_id,)
			)
			conn.execute(
				"UPDATE functions SET url='/admin/api' WHERE code='data_api'"
			)

			# 添加「定时采集」子菜单
			schedule_row = conn.execute("SELECT id FROM functions WHERE code='outlook_schedule'").fetchone()
			if not schedule_row:
				conn.execute(
					"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
					(data_id, "定时采集", "outlook_schedule", "layui-icon-log", "/admin/outlook/schedule", 4, 1)
				)
				sched_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
				admin_role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
				if admin_role:
					conn.execute("INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)", (admin_role["id"], sched_id))

			# 添加「采集日志」子菜单
			log_row = conn.execute("SELECT id FROM functions WHERE code='outlook_log'").fetchone()
			if not log_row:
				conn.execute(
					"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
					(data_id, "采集日志", "outlook_log", "layui-icon-file", "/admin/outlook/log", 5, 1)
				)
				log_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
				admin_role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
				if admin_role:
					conn.execute("INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)", (admin_role["id"], log_id))

		# 确保「核心业务」下数字员工菜单存在
		biz_row = conn.execute("SELECT id FROM functions WHERE parent_id=0 AND code='business'").fetchone()
		if biz_row:
			biz_id = biz_row["id"]
			emp_row = conn.execute("SELECT id FROM functions WHERE code='biz_employees'").fetchone()
			if not emp_row:
				conn.execute(
					"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
					(biz_id, "数字员工", "biz_employees", "layui-icon-user", "/admin/agent", 2, 1)
				)
				emp_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
				admin_role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
				if admin_role:
					conn.execute("INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)", (admin_role["id"], emp_id))
			else:
				conn.execute("UPDATE functions SET url='/admin/agent', parent_id=?, sort_order=2 WHERE code='biz_employees'", (biz_id,))

		# 把「系统」一级菜单 sort_order 改为 5
		conn.execute("UPDATE functions SET sort_order=5 WHERE parent_id=0 AND code='system'")

		# 新增「数智大屏」一级菜单（sort_order=4，放在系统前面）
		db_row = conn.execute("SELECT id FROM functions WHERE parent_id=0 AND code='biz_dashboard'").fetchone()
		if not db_row:
			conn.execute(
				"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
				(0, "数智大屏", "biz_dashboard", "layui-icon-chart", "", 4, 1)
			)
			db_parent_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
			admin_role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
			# 大屏主页
			conn.execute(
				"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
				(db_parent_id, "数智大屏", "biz_dashboard_home", "layui-icon-home", "/dashboard", 1, 1)
			)
			home_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
			if admin_role:
				conn.execute("INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)", (admin_role["id"], db_parent_id))
				conn.execute("INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)", (admin_role["id"], home_id))
		else:
			db_parent_id = db_row["id"]
			# 确保子菜单存在
			home_row = conn.execute("SELECT id FROM functions WHERE code='biz_dashboard_home'").fetchone()
			if not home_row:
				conn.execute(
					"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
					(db_parent_id, "数智大屏", "biz_dashboard_home", "layui-icon-home", "/dashboard", 1, 1)
				)
				home_id2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
				admin_role = conn.execute("SELECT id FROM roles WHERE code='admin'").fetchone()
				if admin_role:
					conn.execute("INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)", (admin_role["id"], home_id2))

		# 创建 api_interfaces 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_interfaces'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE api_interfaces(
					id integer PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL,
					code TEXT NOT NULL UNIQUE,
					api_url TEXT NOT NULL,
					method TEXT NOT NULL DEFAULT 'GET',
					response_format TEXT NOT NULL DEFAULT 'JSON',
					request_example TEXT,
					params_schema TEXT,
					headers TEXT,
					description TEXT,
					qps_limit TEXT,
					status INTEGER NOT NULL DEFAULT 1,
					total_calls INTEGER NOT NULL DEFAULT 0,
					last_called_at TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)
		_init_default_api_interfaces(conn)

		# 创建 chat_conversations 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_conversations'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE chat_conversations(
					id integer PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL,
					title TEXT NOT NULL DEFAULT '新对话',
					model_id INTEGER,
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					update_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 chat_messages 表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE chat_messages(
					id integer PRIMARY KEY AUTOINCREMENT,
					conversation_id INTEGER NOT NULL,
					role TEXT NOT NULL,
					content TEXT NOT NULL,
					tool_calls TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# ==================== 智能聊天子系统数据表 ====================

		# 创建 im_conversations 表（会话表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_conversations'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_conversations(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					type TEXT NOT NULL DEFAULT 'private',
					name TEXT,
					creator_id INTEGER,
					avatar TEXT,
					last_message TEXT,
					last_message_at TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 im_conversation_members 表（会话成员表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_conversation_members'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_conversation_members(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					conversation_id INTEGER NOT NULL,
					user_id INTEGER NOT NULL,
					role TEXT NOT NULL DEFAULT 'member',
					join_at TEXT NOT NULL DEFAULT(datetime('now')),
					UNIQUE(conversation_id, user_id)
				)
				"""
			)

		# 创建 im_messages 表（消息表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_messages'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_messages(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					conversation_id INTEGER NOT NULL,
					sender_id INTEGER NOT NULL,
					type TEXT NOT NULL DEFAULT 'text',
					content TEXT NOT NULL,
					status TEXT NOT NULL DEFAULT 'sent',
					is_read INTEGER NOT NULL DEFAULT 0,
					client_msg_id TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)
		else:
			# 检查是否有 client_msg_id 字段
			cursor2 = conn.execute("PRAGMA table_info(im_messages)")
			cols = [r[1] for r in cursor2.fetchall()]
			if 'client_msg_id' not in cols:
				conn.execute("ALTER TABLE im_messages ADD COLUMN client_msg_id TEXT")

		# 创建 im_unread_counts 表（未读消息计数表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_unread_counts'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_unread_counts(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					conversation_id INTEGER NOT NULL,
					user_id INTEGER NOT NULL,
					count INTEGER NOT NULL DEFAULT 0,
					UNIQUE(conversation_id, user_id)
				)
				"""
			)

		# 创建 im_friends 表（好友关系表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_friends'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_friends(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL,
					friend_id INTEGER NOT NULL,
					remark TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					UNIQUE(user_id, friend_id)
				)
				"""
			)

		# 创建 im_friend_requests 表（好友申请表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_friend_requests'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_friend_requests(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					from_user_id INTEGER NOT NULL,
					to_user_id INTEGER NOT NULL,
					message TEXT,
					status TEXT NOT NULL DEFAULT 'pending',
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					update_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 im_group_invites 表（群邀请表）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_group_invites'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_group_invites(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					group_id INTEGER NOT NULL,
					inviter_id INTEGER NOT NULL,
					invitee_id INTEGER NOT NULL,
					status TEXT NOT NULL DEFAULT 'pending',
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					update_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 im_friend_req_reads 表（好友申请已读记录）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_friend_req_reads'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_friend_req_reads(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL,
					req_id INTEGER NOT NULL,
					req_type TEXT NOT NULL,
					read_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 im_group_invite_reads 表（群邀请已读记录）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_group_invite_reads'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_group_invite_reads(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					user_id INTEGER NOT NULL,
					invite_id INTEGER NOT NULL,
					invite_type TEXT NOT NULL,
					read_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# ==================== 群管理功能扩展 ====================

		# im_conversations 表新增字段
		for col, col_def in [
			('is_muted_all', 'INTEGER DEFAULT 0'),
			('allow_join', 'INTEGER DEFAULT 1'),
			('announcement', 'TEXT'),
			('announcement_time', 'TEXT'),
			('announcement_publisher_id', 'INTEGER'),
			('is_deleted', 'INTEGER DEFAULT 0'),
			('deleted_at', 'TEXT'),
		]:
			cursor = conn.execute(f"PRAGMA table_info(im_conversations)")
			existing_cols = [r[1] for r in cursor.fetchall()]
			if col not in existing_cols:
				conn.execute(f"ALTER TABLE im_conversations ADD COLUMN {col} {col_def}")

		# im_conversation_members 表新增字段
		for col, col_def in [
			('mute_until', 'TEXT'),
			('last_speak_at', 'TEXT'),
			('is_deleted', 'INTEGER NOT NULL DEFAULT 0'),
		]:
			cursor = conn.execute(f"PRAGMA table_info(im_conversation_members)")
			existing_cols = [r[1] for r in cursor.fetchall()]
			if col not in existing_cols:
				conn.execute(f"ALTER TABLE im_conversation_members ADD COLUMN {col} {col_def}")

		# im_group_invites 表新增字段
		for col, col_def in [
			('message', 'TEXT DEFAULT ""'),
		]:
			cursor = conn.execute(f"PRAGMA table_info(im_group_invites)")
			existing_cols = [r[1] for r in cursor.fetchall()]
			if col not in existing_cols:
				conn.execute(f"ALTER TABLE im_group_invites ADD COLUMN {col} {col_def}")

		# 将现有群创建者的 role 从 admin 改为 owner
		conn.execute(
			"""
			UPDATE im_conversation_members
			SET role = 'owner'
			WHERE conversation_id IN (SELECT id FROM im_conversations WHERE type='group')
			  AND user_id = (SELECT creator_id FROM im_conversations WHERE type='group' AND id = conversation_id)
			  AND role = 'admin'
			"""
		)

		# 创建 group_announcements 表（公告历史）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='group_announcements'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE group_announcements(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					group_id INTEGER NOT NULL,
					content TEXT NOT NULL,
					publisher_id INTEGER NOT NULL,
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					is_active INTEGER NOT NULL DEFAULT 1
				)
				"""
			)

		# 创建 announcement_confirmations 表（公告确认记录）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='announcement_confirmations'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE announcement_confirmations(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					announcement_id INTEGER NOT NULL,
					group_id INTEGER NOT NULL,
					user_id INTEGER NOT NULL,
					create_at TEXT NOT NULL DEFAULT(datetime('now')),
					UNIQUE(announcement_id, user_id)
				)
				"""
			)

		# 创建 group_operation_logs 表（操作日志）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='group_operation_logs'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE group_operation_logs(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					group_id INTEGER NOT NULL,
					operator_id INTEGER NOT NULL,
					operation_type TEXT NOT NULL,
					target_id INTEGER,
					detail TEXT,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# 创建 im_files 表（文件去重存储）
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='im_files'")
		if not cursor.fetchone():
			conn.execute(
				"""
				CREATE TABLE im_files(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					file_name TEXT NOT NULL,
					file_size INTEGER NOT NULL,
					file_hash TEXT NOT NULL UNIQUE,
					file_ext TEXT NOT NULL DEFAULT '',
					mime_type TEXT DEFAULT '',
					storage_path TEXT NOT NULL,
					uploader_id INTEGER NOT NULL,
					ref_count INTEGER NOT NULL DEFAULT 1,
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

		# im_files 表字段升级

		# 数据迁移：将 im_messages 中旧的 UTC 时间转为本地时间（仅执行一次）
		import datetime
		need_migrate = conn.execute("SELECT COUNT(*) as cnt FROM im_messages WHERE create_at > datetime('now', '+7 hours')").fetchone()['cnt']
		if need_migrate == 0:
			rows = conn.execute("SELECT id, create_at FROM im_messages").fetchall()
			if rows:
				for row in rows:
					try:
						utc_dt = datetime.datetime.strptime(row['create_at'], '%Y-%m-%d %H:%M:%S')
						local_dt = utc_dt + datetime.timedelta(hours=8)
						conn.execute("UPDATE im_messages SET create_at=? WHERE id=?", (local_dt.strftime('%Y-%m-%d %H:%M:%S'), row['id']))
					except (ValueError, KeyError):
						pass

		# 初始化默认数据
		_init_default_data(conn)

		# 创建自动化工作流表
		cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auto_workflows'")
		if not cursor.fetchone():
			conn.execute("""
				CREATE TABLE auto_workflows(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL,
					description TEXT DEFAULT '',
					steps TEXT NOT NULL DEFAULT '[]',
					cron_expression TEXT DEFAULT '',
					is_enabled INTEGER DEFAULT 1,
					last_run_at TEXT,
					last_result TEXT DEFAULT '',
					create_at TEXT DEFAULT (datetime('now'))
				)
			""")
			conn.execute("""
				CREATE TABLE workflow_logs(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					workflow_id INTEGER NOT NULL,
					status TEXT DEFAULT 'running',
					result TEXT DEFAULT '',
					started_at TEXT DEFAULT (datetime('now')),
					finished_at TEXT
				)
			""")

		# 清理已删除的功能菜单（避免已有数据库残留）
		for del_code in ('biz_dashboard_components', 'sys_stats'):
			del_row = conn.execute("SELECT id FROM functions WHERE code=?", (del_code,)).fetchone()
			if del_row:
				conn.execute("DELETE FROM role_functions WHERE function_id=?", (del_row["id"],))
				conn.execute("DELETE FROM functions WHERE id=?", (del_row["id"],))

		# 迁移：添加毒鸡汤助手（如果不存在）
		existing = conn.execute("SELECT id FROM assistants WHERE assistant_code=?", ("poison_chicken_soup",)).fetchone()
		if not existing:
			max_sort = conn.execute("SELECT COALESCE(MAX(sort_order),0) as ms FROM assistants").fetchone()["ms"]
			conn.execute(
				"INSERT INTO assistants(assistant_name,assistant_code,icon,prompt_template,model_id,sort_order,is_enabled,api_key,api_url,description,category,api_interface_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
				(
					"毒鸡汤助手", "poison_chicken_soup", "fas fa-skull",
					"你是毒鸡汤助手，专长是用尖锐而幽默的方式讲出扎心的大实话。\n"
					"请根据用户的输入，随机回复一条毒鸡汤语录。\n"
					"毒鸡汤应当：\n"
					"1. 简短有力，一两句话即可\n"
					"2. 带有黑色幽默或反讽色彩\n"
					"3. 既要扎心又要让人会心一笑\n"
					"4. 可以根据用户输入内容进行针对性回复\n"
					"5. 不要过于恶毒或人身攻击，保持幽默底线\n\n"
					"示例风格：\n"
					"- \u201c努力不一定成功，但不努力一定很舒服。\u201d\n"
					"- \u201c你以为你是主角，其实你连NPC都不如。\u201d\n"
					"- \u201c加油，你是最胖的！\u201d",
					None, max_sort + 1, 1, "", "", "随机回复毒鸡汤语句，让人清醒的扎心语录", "AI", None
				)
			)
		conn.commit()