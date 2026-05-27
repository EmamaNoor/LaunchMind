from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DEEPSEEK_API_KEY: str
    UPSTASH_REDIS_URL: str
    GITHUB_TOKEN: str
    GITHUB_REPO: str
    SLACK_BOT_TOKEN: str
    SLACK_CHANNEL: str = "#launches"
    SENDGRID_API_KEY: str
    SENDGRID_FROM_EMAIL: str
    TEST_EMAIL: str
