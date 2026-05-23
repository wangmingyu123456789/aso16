import hashlib
import secrets
import sqlite3

from app.models.db import get_connection

#密码加密方法
def _hash_password(password:str,salt:bytes)->str:
	dk = hashlib.pbkdf2_hmac("sha256",password.encode('utf-8'),salt,100_000)
	return dk.hex()

#用户对象表
class UserRepository:
	#创建用户方法
	@staticmethod
	def create_user(username:str,password:str)->bool:
		salt = secrets.token_bytes(16)
		password_hash = _hash_password(password,salt)

		try:
			with get_connection() as conn:
				conn.execute("insert into users(username,password_hash,salt) values(?,?,?)",(username,password_hash,salt.hex()),)
				return True
		except sqlite3.IntegrityError:
			return False

	#通过用户名检索用户信息的方法
	@staticmethod
	def get_user_by_username(username:str):
		with get_connection() as conn:
			row = conn.execute("select id,username,password_hash,salt from users where username = ?",(username,)).fetchone()
		return row

	#验证用户名和密码的方法
	@staticmethod
	def verify_user(username:str,password:str)->bool:
		row = UserRepository.get_user_by_username(username)
		if not row:
			return False

		salt = bytes.fromhex(row["salt"])
		return _hash_password(password,salt) == row["password_hash"]
