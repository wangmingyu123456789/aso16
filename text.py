from app.models.db import init_db
from app.models.user import UserRepository

init_db()
print("新增",UserRepository.create_user("admin","123456"))
print("根据条件查询",UserRepository.get_user_by_username("admin"))
print("验证登录",UserRepository.verify_user("admin","123456"))
# print("新增",UserRepository.create_user("admin1","123456"))
# print("新增",UserRepository.create_user("admin2","123456"))