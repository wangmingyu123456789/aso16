# 数据库链接与建表
import os
import json
import sqlite3
def _projiect_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir,os.pardir))
DB_PATH = os.path.join(_projiect_root(),"database","app.db")

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
					title TEXT NOT NULL,
					url TEXT,
					content TEXT,
					author TEXT,
					publish_date TEXT,
					raw_html TEXT,
					ai_processed INTEGER NOT NULL DEFAULT 0,
					collect_status TEXT NOT NULL DEFAULT 'success',
					create_at TEXT NOT NULL DEFAULT(datetime('now'))
				)
				"""
			)

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
				 'div.result', 'h3', 'h3 a', 'div.content-right > span', 'span.c-color-gray2', 'p.author-text',
				 10, 0, 1,
				 '请对采集到的新闻标题和内容进行AI清洗，去除无关信息，提取核心要点，并以JSON格式返回：[{"title":"标题","content":"摘要","author":"作者","date":"日期"}]',
				 1, '百度新闻搜索引擎采集源')
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

		# 初始化默认数据
		_init_default_data(conn)
		conn.commit()

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
		(0, '数据管理', 'data', 'layui-icon-table', '', 3, 1),
		(0, '系统', 'system', 'layui-icon-component', '', 4, 1),
		# 二级菜单
		(1, '系统首页', 'base_index', 'layui-icon-home', '/admin', 1, 1),
		(1, '用户管理', 'base_users', 'layui-icon-username', '/admin/users', 2, 1),
		(1, '角色管理', 'base_roles', 'layui-icon-group', '/admin/roles', 3, 1),
		(1, '功能管理', 'base_functions', 'layui-icon-menu-fill', '/admin/functions', 4, 1),
		(1, '权限管理', 'base_permissions', 'layui-icon-auz', '/admin/permissions', 5, 1),
		(2, '模型引擎', 'biz_models', 'layui-icon-engine', '/admin/models', 1, 1),
		(2, '数字员工', 'biz_employees', 'layui-icon-user', '/admin/employees', 2, 1),
		(2, '瞭望管理', 'biz_outlook', 'layui-icon-read', '/admin/outlook', 3, 1),
		(3, '数据仓库', 'data_warehouse', 'layui-icon-table', '/admin/warehouse', 1, 1),
		(3, '接口管理', 'data_api', 'layui-icon-link', '/admin/api', 2, 1),
		(4, '系统设置', 'sys_settings', 'layui-icon-set', '/admin/settings', 1, 1),
		(4, '系统统计', 'sys_stats', 'layui-icon-chart', '/admin/stats', 2, 1),
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

		# outlook_data 添加 task_id 字段
		cursor = conn.execute("PRAGMA table_info(outlook_data)")
		data_cols = [row[1] for row in cursor.fetchall()]
		if len(data_cols) > 0 and 'task_id' not in data_cols:
			conn.execute("ALTER TABLE outlook_data ADD COLUMN task_id INTEGER NOT NULL DEFAULT 0")

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

		# 初始化默认数据
		_init_default_data(conn)
		conn.commit()