import hashlib
import secrets
import sqlite3

from app.models.db import get_connection

def _hash_password(password:str,salt:bytes)->str:
	dk = hashlib.pbkdf2_hmac("sha256",password.encode('utf-8'),salt,100_000)
	return dk.hex()

class UserRepository:
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

	@staticmethod
	def get_user_by_username(username:str):
		with get_connection() as conn:
			row = conn.execute("select id,username,password_hash,salt from users where username = ?",(username,)).fetchone()
		return row

	@staticmethod
	def verify_user(username:str,password:str)->bool:
		row = UserRepository.get_user_by_username(username)
		if not row:
			return False
		salt = bytes.fromhex(row["salt"])
		return _hash_password(password,salt) == row["password_hash"]

	@staticmethod
	def create_admin_user(username:str,password:str,role:str='admin')->bool:
		salt = secrets.token_bytes(16)
		password_hash = _hash_password(password,salt)
		try:
			with get_connection() as conn:
				conn.execute(
					"insert into users(username,password_hash,salt,role) values(?,?,?,?)",
					(username,password_hash,salt.hex(),role)
				)
				return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def verify_admin_user(username:str,password:str)->bool:
		with get_connection() as conn:
			row = conn.execute(
				"select id,username,password_hash,salt,role,status from users where username = ? and role = 'admin'",
				(username,)
			).fetchone()
		if not row:
			return False
		if row["status"] != 1:
			return False
		salt = bytes.fromhex(row["salt"])
		return _hash_password(password,salt) == row["password_hash"]

	@staticmethod
	def get_user_list(page:int=1,page_size:int=20,keyword:str=None)->dict:
		offset = (page - 1) * page_size
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"select count(*) as total from users where username like ?",
					(f'%{keyword}%',)
				).fetchone()
				total = count_row["total"]
				rows = conn.execute(
					"select id,username,role,status,create_at from users where username like ? order by id desc limit ? offset ?",
					(f'%{keyword}%', page_size, offset)
				).fetchall()
			else:
				count_row = conn.execute("select count(*) as total from users").fetchone()
				total = count_row["total"]
				rows = conn.execute(
					"select id,username,role,status,create_at from users order by id desc limit ? offset ?",
					(page_size, offset)
				).fetchall()
		return {
			'total': total,
			'data': [dict(row) for row in rows],
			'page': page,
			'page_size': page_size,
			'total_pages': (total + page_size - 1) // page_size if total > 0 else 1
		}

	@staticmethod
	def delete_user(user_id:int)->bool:
		try:
			with get_connection() as conn:
				conn.execute("delete from users where id = ?", (user_id,))
				return True
		except Exception:
			return False

	@staticmethod
	def delete_users(user_ids:list)->bool:
		try:
			with get_connection() as conn:
				conn.execute("delete from users where id in ({})".format(','.join(['?']*len(user_ids))), user_ids)
				return True
		except Exception:
			return False

	@staticmethod
	def update_user(user_id:int, username:str=None, password:str=None, role:str=None, status:int=None)->bool:
		updates = []
		params = []
		if username is not None:
			updates.append("username = ?")
			params.append(username)
		if password is not None:
			salt = secrets.token_bytes(16)
			password_hash = _hash_password(password,salt)
			updates.append("password_hash = ?")
			params.append(password_hash)
			updates.append("salt = ?")
			params.append(salt.hex())
		if role is not None:
			updates.append("role = ?")
			params.append(role)
		if status is not None:
			updates.append("status = ?")
			params.append(status)
		if not updates:
			return False
		params.append(user_id)
		try:
			with get_connection() as conn:
				conn.execute(
					"update users set {} where id = ?".format(','.join(updates)),
					params
				)
				return True
		except Exception:
			return False

	@staticmethod
	def get_user_by_id(user_id:int):
		with get_connection() as conn:
			row = conn.execute(
				"select id,username,role,status,create_at from users where id = ?",
				(user_id,)
			).fetchone()
		return row
