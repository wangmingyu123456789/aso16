"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # 数据库配置
    ACTIVE_DATABASE: str = os.getenv("ACTIVE_DATABASE", "sqlite")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./data/ctos.db")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "ctos")

    # JWT配置
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "ctos-jwt-secret-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    # 应用配置
    APP_NAME: str = os.getenv("APP_NAME", "CToS2智能问数系统")
    ENV: str = os.getenv("ENV", "development")
    DB_TYPE: str = os.getenv("ACTIVE_DATABASE", "sqlite")
    DB_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    DB_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    DB_NAME: str = os.getenv("MYSQL_DATABASE", "ctos")
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    EXTERNAL_PORT: int = int(os.getenv("EXTERNAL_PORT", "8080"))  # 外部服务端口
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    SYSTEM_NAME: str = os.getenv("SYSTEM_NAME", "CToS智能系统")
    EXTERNAL_BASE_URL: str = os.getenv("EXTERNAL_BASE_URL", "http://localhost:8080")  # 外部访问的基础URL
    SYSTEM_BASE_URL: str = os.getenv("SYSTEM_BASE_URL", "http://localhost:8000")  # 系统基础URL

    @property
    def database_url(self) -> str:
        if self.ACTIVE_DATABASE == "mysql":
            return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        # SQLite
        os.makedirs(os.path.dirname(self.SQLITE_PATH) if os.path.dirname(self.SQLITE_PATH) else ".", exist_ok=True)
        return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"


    @property
    def is_mysql(self) -> bool:
        return self.ACTIVE_DATABASE == "mysql"

settings = Settings()
