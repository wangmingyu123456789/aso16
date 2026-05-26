import tornado.web
from app.controllers.base import BaseHandler

class IndexHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		from app.models.db import get_connection
		with get_connection() as conn:
			row = conn.execute("SELECT role FROM users WHERE username=?", (self.current_user,)).fetchone()
		if row and row["role"] in ("admin", "manager"):
			self.redirect("/admin")
		else:
			self.redirect("/chat")