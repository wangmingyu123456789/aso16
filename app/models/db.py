# 数据库链接与建表
import os
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
			# 将现有的admin用户设置为允许登录
			conn.execute("UPDATE users SET can_login_admin=1 WHERE username='admin'")

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