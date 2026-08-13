from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 100   # 60 min quiz + 40 min buffer — P0-8
    ADMIN_SECRET: str
    PORT: int = 3000
    QUIZ_ID: int = 1
    TUNNEL_DOMAIN: str = ""
    EASTER_EGG_SECRET: str
    EASTER_EGG_FLAG: str

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
