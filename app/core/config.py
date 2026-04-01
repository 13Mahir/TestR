"""
Configuration settings block for the TestR.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_SECRET_KEY: str
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080

    DB_HOST: Optional[str] = None
    DB_PORT: int = 3306
    DB_NAME: str = "testr"
    DB_USER: Optional[str] = None
    DB_PASSWORD: str = ""

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
        """Assembles the asyncio MySQL connection string."""
        import urllib.parse
        host = self.MYSQLHOST or self.DB_HOST or "127.0.0.1"
        port = self.MYSQLPORT or self.DB_PORT
        db_name = self.MYSQLDATABASE or self.DB_NAME
        user = self.MYSQLUSER or self.DB_USER or "root"
        password = self.MYSQLPASSWORD or self.DB_PASSWORD or ""
        
        # Ensure password is URL encoded for the connection string
        pw = urllib.parse.quote_plus(password)
        return f"mysql+aiomysql://{user}:{pw}@{host}:{port}/{db_name}"

    @property
    def is_production(self) -> bool:
        """Returns True if the application environment is production."""
        return self.APP_ENV == "production"


settings = Settings()
