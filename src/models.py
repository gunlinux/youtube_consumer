from enum import IntEnum

from pydantic import BaseModel, Field


class Source(IntEnum):
    """Message source platform."""

    TWITCH = 0
    YOUTUBE = 1


class MessageCreate(BaseModel):
    """Input payload posted to stream_stats (same contract as stream_stats_consumer)."""

    body: str = Field(..., description="Текст сообщения")
    source: Source = Field(..., description="0 twitch, 1 youtube")
    message_id: str = Field(..., description="id внешней системы")
    author_id: str = Field(..., description="ID чаттерса")
    stream_id: str = Field(..., description="ID стрима")
    channel_id: str = Field(..., description="Id канала")
