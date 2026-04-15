"""
Configuration settings block for the TestR.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import urllib.parse


class Settings(BaseSettings):
    APP_SECRET_KEY: str
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = Field(default=8080, alias="PORT")
    ALLOWED_HOSTS: list[str] = ["*"]
    TRUST_PROXY: bool = True  # Essential for Cloud Run behind a load balancer

    DB_HOST: Optional[str] = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "testr"
    DB_USER: Optional[str] = "root"
    DB_PASSWORD: Optional[str] = ""
    JWT_ALGORITHM: str = "HS256"

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]

    # Railway Auto-injected variables for seamless deployment
    MYSQLHOST: Optional[str] = None
    MYSQLPORT: Optional[int] = None
    MYSQLDATABASE: Optional[str] = None
    MYSQLUSER: Optional[str] = None
    MYSQLPASSWORD: Optional[str] = None

    GCS_BUCKET_NAME: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ADMIN_EMAIL: str = "admin@clg.ac.in"
    ADMIN_INITIAL_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def db_url(self) -> str:
        # Priority: Railway/Custom Variables -> Default Settings
        host = self.MYSQLHOST or self.DB_HOST or "localhost"
        port = self.MYSQLPORT or self.DB_PORT or 3306
        db_name = self.MYSQLDATABASE or self.DB_NAME or "testr"
        user = self.MYSQLUSER or self.DB_USER or "root"
        password = self.MYSQLPASSWORD or self.DB_PASSWORD or ""

        pw = urllib.parse.quote_plus(password)
        
        if host == "sqlite":
            return f"sqlite+aiosqlite:///{db_name}.db"

        # Detect Cloud SQL connection (contains colon but isn't a URL)
        # Cloud Run format: project:region:instance
        if ":" in host and not host.startswith(("http://", "https://")):
            socket_path = host if host.startswith("/cloudsql/") else f"/cloudsql/{host}"
            return f"mysql+aiomysql://{user}:{pw}@/{db_name}?unix_socket={socket_path}"

        # Standard TCP connection
        return f"mysql+aiomysql://{user}:{pw}@{host}:{port}/{db_name}"

    @property
    def is_production(self) -> bool:
        """Returns True if the application environment is production."""
        return self.APP_ENV == "production"


settings = Settings()
