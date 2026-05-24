import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.user import UserRepository

class AdminUserListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/user_list.html",title="用户管理",username=self.current_user,current_page='users')

class AdminUserApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page","1"))
		keyword = self.get_argument("keyword","")
		result = UserRepository.get_user_list(page=page,page_size=20,keyword=keyword if keyword else None)
		self.set_header("Content-Type","application/json")
		self.write(json.dumps({
			"code":0,
			"data":result["data"],
			"total":result["total"],
			"page":result["page"],
			"page_size":result["page_size"],
			"total_pages":result["total_pages"]
		}))

class AdminUserAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		username = (self.get_body_argument("username","")or"").strip()
		password = self.get_body_argument("password","")
		role = self.get_body_argument("role","user")
		status = int(self.get_body_argument("status","1"))
		if not username or not password:
			return self.write({"code":1,"msg":"用户名和密码不能为空"})
		salt = __import__("secrets").token_bytes(16)
		password_hash = __import__("hashlib").pbkdf2_hmac("sha256",password.encode("utf-8"),salt,100_000).hex()
		try:
			from app.models.db import get_connection
			with get_connection() as conn:
				conn.execute(
					"insert into users(username,password_hash,salt,role,status) values(?,?,?,?,?)",
					(username,password_hash,salt.hex(),role,status)
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
		if not user_id:
			return self.write({"code":1,"msg":"用户ID不能为空"})
		# 检查是否为超级管理员用户
		from app.models.db import get_connection
		with get_connection() as conn:
			user = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
		if user and user["username"] == "admin":
			# 超级管理员只能修改密码
			if not password:
				return self.write({"code":1,"msg":"超级管理员必须设置密码"})
			if UserRepository.update_user(user_id, password=password):
				return self.write({"code":0,"msg":"密码修改成功"})
			return self.write({"code":1,"msg":"密码修改失败"})
		if not username:
			return self.write({"code":1,"msg":"用户名不能为空"})
		update_params = {"username":username,"role":role,"status":status}
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
