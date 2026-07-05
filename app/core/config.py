from pydantic_settings import BaseSettings,SettingsConfigDict

class Setting(BaseSettings):
    DATABASE_URL:str
    SECRET_KEY:str
    model_config = SettingsConfigDict(env_file=".env")

settings = Setting()
