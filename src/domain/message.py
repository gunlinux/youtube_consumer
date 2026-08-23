import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Message:
    id: str
    author: str
    author_id: str
    text: str
    timestamp: datetime
    platform: str
    stream_id: str = ""

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(
            id=str(uuid.uuid4()),
            author="system",
            author_id="",
            text=text,
            timestamp=datetime.now(UTC),
            platform="system",
        )
