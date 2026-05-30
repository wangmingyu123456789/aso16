import json
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.im import IMRepository


class AdminIMFilesHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/im_files.html", title="文件管理", username=self.current_user, current_page='im_files')


class AdminIMFilesApiHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("limit", "20"))
        keyword = self.get_argument("keyword", "")
        file_type = self.get_argument("file_type", "")
        uploader_id = int(self.get_argument("uploader_id", "0"))
        result = IMRepository.get_all_files_admin(page, page_size, keyword, file_type, uploader_id)
        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["data"]
        })


class AdminIMFilesDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        file_id = data.get("file_id", 0)
        if not file_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 1, "msg": "参数错误"})
            return
        ok = IMRepository.admin_delete_file(file_id)
        if ok:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "msg": "删除成功"})
        else:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 1, "msg": "删除失败（文件引用数大于0，无法删除）"})


class AdminIMFilesStatsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        stats = IMRepository.get_file_stats()
        users = IMRepository.get_users_dropdown()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": stats, "users": users})
