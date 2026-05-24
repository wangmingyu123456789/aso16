from app.models.db import init_db,upgrade_db
from app.models.user import UserRepository

init_db()
upgrade_db()

admin_result = UserRepository.create_admin_user("admin","admin888")
print("初始化管理员 admin/admin888:",admin_result)

test_result = UserRepository.create_user("testuser","123456")
print("新增测试用户:",test_result)

print("查询管理员:",UserRepository.get_user_by_username("admin"))
print("验证管理员登录:",UserRepository.verify_admin_user("admin","admin888"))
print("获取用户列表:",UserRepository.get_user_list(page=1,page_size=20))
