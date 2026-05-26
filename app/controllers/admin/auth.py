import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.user import UserRepository

class AdminLoginHandler(AdminBaseHandler):
	def get(self):
		self.render("admin/login.html",title="系统登录",error=None)

	def post(self):
		username=(self.get_body_argument("username","")or"").strip()
		password=self.get_body_argument("password","")
		login_type=self.get_body_argument("login_type","user")

		if not username or not password:
			self.set_status(400)
			return self.render("admin/login.html",title="系统登录",error="账号或密码不能为空")

		if login_type == "admin":
			if not UserRepository.verify_admin_user(username,password):
				self.set_status(401)
				return self.render("admin/login.html",title="系统登录",error="管理员账号或密码错误，或账号已被禁用")
			self.set_secure_cookie("admin_username",username)
		else:
			if not UserRepository.verify_admin_user(username,password):
				self.set_status(401)
				return self.render("admin/login.html",title="系统登录",error="用户未授权，请联系管理员授权后登录")
			self.set_secure_cookie("admin_username",username)

		self.redirect("/admin")

class AdminLogoutHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		self.clear_cookie("admin_username")
		self.redirect("/admin/login")
