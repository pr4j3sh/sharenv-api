from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://127.0.0.1:27017/sharenv_test"


settings = Settings()
