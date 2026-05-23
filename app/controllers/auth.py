# 认证相关的 controller(登录/注册/退出)

# 通过handler 展示 mvc 中 controller层如何接收表单，校验输入，调用model层，再渲染view层 或 跳转
# 登录态 用 secure cookie 保存 username

import tornado.web
from app.controllers.base import BaseHandler
from app.models.user import UserRepository

class LoginHandler(BaseHandler):
	# /auth/login
	# get:渲染登录页
	# post:校验用户名和密码，通过后写入secure cookie 并跳转到目标页
	def get(self):
		# self.write(f"""<h3>登录</h3>
		# 	<form method="post" action="/auth/login">
		# 	<input name="username">
		# 	<input name="password">
		# 	<button type="submit">登录admin</button>
		# 	{self.xsrf_form_html()}
		# 	</form>
		# """)
		self.render("login.html",title="登录",error=None)

	def post(self):
		username=(self.get_body_argument("username","")or"").strip()
		password=self.get_body_argument("password","")
		if not username or not password:
			self.set_status(400)
			# return self.write(f"""<h3>登录</h3>
			# 用户名不能为空，输入无效数据
			# <form method="post" action="/auth/login">
			# <input name="username">
			# <input name="password">
			# <button type="submit">登录admin</button>
			# {self.xsrf_form_html()}
			# </form>
			# """)
			return self.render("login.html",title="登录",error="用户名或密码不能为空或输入无效数据")

		if not UserRepository.verify_user(username,password):
			self.set_status(401)
			# return self.write(f"""<h3>登录</h3>
			# 用户名或密码错误
			# <form method="post" action="/auth/login">
			# <input name="username">
			# <input name="password">
			# <button type="submit">登录admin</button>
			# {self.xsrf_form_html()}
			# </form>
			# """)
			return self.render("login.html",title="登录",error="用户名或密码错误")

		self.set_secure_cookie("username",username)
		# self.write(f"登录成功,欢迎:{username}")
		self.redirect("/")

class LogoutHandler(BaseHandler):
	def post(self):
		self.clear_cookie("username")
		self.redirect("/auth/login")
