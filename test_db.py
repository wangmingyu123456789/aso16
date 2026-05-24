from app.models.db import init_db, upgrade_db
from app.models.user import UserRepository

init_db()
upgrade_db()
print('DB OK')
print('Admin verify:', UserRepository.verify_admin_user('admin', 'admin888'))
print('User verify:', UserRepository.verify_user('admin', 'admin888'))
