# 认证相关的 controller(登录/注册/退出)

# 通过handler 展示 mvc 中 controller层如何接收表单，校验输入，调用model层，再渲染view层 或 跳转
# 登录态 用 secure cookie 保存 username

import tornado.web
import urllib.parse
from app.controllers.base import BaseHandler
from app.models.user import UserRepository

class LoginHandler(BaseHandler):
	def get(self):
		self.render("user_login.html",title="登录")

	def post(self):
		username=(self.get_body_argument("username","")or"").strip()
		password=self.get_body_argument("password","")
		if not username:
			self.redirect("/auth/login?error="+urllib.parse.quote("请填写用户名"))
			return
		if not password:
			self.redirect("/auth/login?error="+urllib.parse.quote("请填写密码"))
			return
		user = UserRepository.get_user_by_username(username)
		if not user:
			self.redirect("/auth/login?error="+urllib.parse.quote("用户还未注册"))
			return
		if not UserRepository.verify_user(username,password):
			self.redirect("/auth/login?error="+urllib.parse.quote("用户名或密码填写错误"))
			return
		self.set_secure_cookie("username",username)
		self.redirect("/chat")

class RegisterHandler(BaseHandler):
	def get(self):
		self.render("register.html",title="注册")

	def post(self):
		username=(self.get_body_argument("username","")or"").strip()
		password=self.get_body_argument("password","")
		password2=self.get_body_argument("password2","")

		err = None
		if not username or not password:
			err = "用户名或密码不能为空"
		elif len(username) < 2:
			err = "用户名至少2个字符"
		elif len(password) < 6:
			err = "密码至少6位"
		elif password != password2:
			err = "两次密码不一致"

		if err:
			self.redirect("/auth/register?error="+urllib.parse.quote(err))
			return

		from app.models.db import get_connection
		with get_connection() as conn:
			exist = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
			if exist:
				self.redirect("/auth/register?error="+urllib.parse.quote("用户名已存在"))
				return

		if UserRepository.create_user(username, password):
			from app.models.db import get_connection
			with get_connection() as conn:
				conn.execute("UPDATE users SET role='user' WHERE username=?", (username,))
			self.redirect("/auth/login?registered=1")
		else:
			self.redirect("/auth/register?error="+urllib.parse.quote("注册失败，请重试"))

class LogoutHandler(BaseHandler):
	def post(self):
		self.clear_cookie("username")
		self.redirect("/auth/login")
