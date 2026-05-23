#Controller 公共基础类 (BaseHandler)
"""
在tornado中
- 每一个Url对应一个RequestHandler 可以理解为Controller
- RequestHandler 提供 post / get 等方法来处理http请求

本程序可以提供一个统一的基础类，用于处理一些公共业务，如登录台的处理或获得逻辑，供其他Handler继承使用
"""
import tornado.web
class BaseHandler(tornado.web.RequestHandler):
	#公共类的用户态认证机制：
	# - 框架会通过 xxx() 的返回值来判断是否“已经登录”
	# - 如果返回None 则 @tornado.web.authenticated 触发器跳到指定的录音URL：login_url
	def get_current_user(self):
		# 返回当前登录用户的字符串 或 None
		usernaame = self.get_secure_cookie("username")
		if not usernaame:
			return None
		return usernaame.decode('utf-8')
