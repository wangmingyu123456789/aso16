"""通用工具函数"""
import json
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ctos")

def success_response(data: Any = None, message: str = "ok", status_code: int = 200) -> JSONResponse:
    """统一成功响应"""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": 0,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
    )

def error_response(message: str = "error", status_code: int = 400, code: int = -1) -> JSONResponse:
    """统一错误响应"""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": None,
            "timestamp": datetime.now().isoformat()
        }
    )

class AppException(HTTPException):
    """自定义业务异常"""
    def __init__(self, message: str, status_code: int = 400, code: int = -1):
        self.code = code
        super().__init__(status_code=status_code, detail=message)

def parse_json_field(value: Optional[str], default: Any = None) -> Any:
    """安全解析JSON字段"""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default

def now_str() -> str:
    """当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str() -> str:
    """今日日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def hash_password(password: str) -> str:
    """使用 PBKDF2-SHA256 哈希密码"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    parts = hashed.split('$')
    if len(parts) != 2:
        return False
    salt, stored_hash = parts
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return pwd_hash.hex() == stored_hash
