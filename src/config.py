from pydantic import AmqpDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    youtube_channel: str = ""
    amqp_dsn: AmqpDsn = AmqpDsn("amqp://user:password@localhost:5672")
    amqp_exchange: str = "messages"
    amqp_reconnect_delay: float = 5.0

    model_config = SettingsConfigDict(
        env_prefix="", env_file=".env", env_file_encoding="utf-8"
    )
