import tornado.web
from app.controllers.admin.base import AdminBaseHandler

class AdminSettingsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/settings.html", title="系统设置", username=self.current_user, current_page='settings')
