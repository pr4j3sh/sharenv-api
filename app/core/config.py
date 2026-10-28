from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    DATABASE: str = "sharenv_test"


settings = Settings()
