import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.user import UserRepository

class AdminUserListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		# 获取所有角色供前端使用
		from app.models.permission import RoleRepository
		roles = RoleRepository.get_all_roles()
		self.render("admin/user_list.html",title="用户管理",username=self.current_user,current_page='users',roles=roles,roles_json=json.dumps(roles))

class AdminUserRolesApiHandler(AdminBaseHandler):
	"""获取角色列表API"""
	@tornado.web.authenticated
	def get(self):
		from app.models.permission import RoleRepository
		roles = RoleRepository.get_all_roles()
		self.set_header("Content-Type","application/json")
		self.write(json.dumps({
			"code":0,
			"data":roles
		}))

class AdminUserApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page","1"))
		# Layui 传递的是 limit 参数，优先使用 limit
		limit_param = self.get_argument("limit", None)
		if limit_param:
			page_size = int(limit_param)
		else:
			page_size = int(self.get_argument("page_size","4"))
		
		keyword = self.get_argument("keyword","")
		
		# 调试日志
		import logging
		logging.info(f"分页参数：page={page}, page_size={page_size}, limit={limit_param}, keyword={keyword}")
		
		result = UserRepository.get_user_list(page=page,page_size=page_size,keyword=keyword if keyword else None)
		self.set_header("Content-Type","application/json")
		self.write({
			"code": 0,
			"msg": "",
			"count": result["total"],
			"data": result["data"],
			"page": result["page"]
		})

class AdminUserAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		username = (self.get_body_argument("username","")or"").strip()
		password = self.get_body_argument("password","")
		role = self.get_body_argument("role","user")
		status = int(self.get_body_argument("status","1"))
		can_login_admin = int(self.get_body_argument("can_login_admin","0"))
		if not username or not password:
			return self.write({"code":1,"msg":"用户名和密码不能为空"})
		if username.lower() == "admin":
			return self.write({"code":1,"msg":"不能创建用户名为admin的用户"})
		salt = __import__("secrets").token_bytes(16)
		password_hash = __import__("hashlib").pbkdf2_hmac("sha256",password.encode("utf-8"),salt,100_000).hex()
		try:
			from app.models.db import get_connection
			with get_connection() as conn:
				conn.execute(
					"insert into users(username,password_hash,salt,role,status,can_login_admin) values(?,?,?,?,?,?)",
					(username,password_hash,salt.hex(),role,status,can_login_admin)
				)
			return self.write({"code":0,"msg":"新增成功"})
		except Exception as e:
			return self.write({"code":1,"msg":"新增失败："+str(e)})

class AdminUserEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		user_id = int(self.get_body_argument("id","0"))
		username = (self.get_body_argument("username","")or"").strip()
		password = self.get_body_argument("password","")
		role = self.get_body_argument("role","user")
		status = int(self.get_body_argument("status","1"))
		can_login_admin = int(self.get_body_argument("can_login_admin","0"))
		if not user_id:
			return self.write({"code":1,"msg":"用户ID不能为空"})
		# 获取当前登录用户的角色
		current_role = self.get_current_user_role()
		# 获取目标用户信息
		from app.models.db import get_connection
		with get_connection() as conn:
			target_user = conn.execute("SELECT username,role FROM users WHERE id=?", (user_id,)).fetchone()
		if not target_user:
			return self.write({"code":1,"msg":"用户不存在"})
		# 超级管理员用户（username='admin'）只能由超级管理员修改
		if target_user["username"] == "admin" and current_role != 'admin':
			return self.write({"code":1,"msg":"只有超级管理员可以修改admin用户"})
		if target_user["username"] == "admin":
			# 超级管理员只能修改密码
			if not password:
				return self.write({"code":1,"msg":"超级管理员必须设置密码"})
			if UserRepository.update_user(user_id, password=password):
				return self.write({"code":0,"msg":"密码修改成功"})
			return self.write({"code":1,"msg":"密码修改失败"})
		# 普通管理员不能修改超级管理员角色用户
		if target_user["role"] == 'admin' and current_role != 'admin':
			return self.write({"code":1,"msg":"只有超级管理员可以修改超级管理员角色用户"})
		if not username:
			return self.write({"code":1,"msg":"用户名不能为空"})
		if username.lower() == "admin":
			return self.write({"code":1,"msg":"不能使用admin作为用户名"})
		update_params = {"username":username,"role":role,"status":status,"can_login_admin":can_login_admin}
		if password:
			update_params["password"] = password
		if UserRepository.update_user(user_id,**update_params):
			return self.write({"code":0,"msg":"修改成功"})
		return self.write({"code":1,"msg":"修改失败"})

class AdminUserDeleteHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		user_id = int(self.get_body_argument("id","0"))
		if not user_id:
			return self.write({"code":1,"msg":"用户ID不能为空"})
		# 检查是否为超级管理员用户
		from app.models.db import get_connection
		with get_connection() as conn:
			user = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
		if user and user["username"] == "admin":
			return self.write({"code":1,"msg":"超级管理员用户不能删除"})
		if UserRepository.delete_user(user_id):
			return self.write({"code":0,"msg":"删除成功"})
		return self.write({"code":1,"msg":"删除失败"})

class AdminUserBatchDeleteHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		ids_str = self.get_body_argument("ids","")
		try:
			user_ids = json.loads(ids_str)
		except:
			return self.write({"code":1,"msg":"参数错误"})
		if not user_ids:
			return self.write({"code":1,"msg":"请先选择要删除的用户"})
		# 检查是否包含超级管理员用户
		from app.models.db import get_connection
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT username FROM users WHERE id IN ({})".format(','.join(['?']*len(user_ids))),
				user_ids
			).fetchall()
		for row in rows:
			if row["username"] == "admin":
				return self.write({"code":1,"msg":"超级管理员用户不能删除"})
		if UserRepository.delete_users(user_ids):
			return self.write({"code":0,"msg":"批量删除成功"})
		return self.write({"code":1,"msg":"批量删除失败"})
