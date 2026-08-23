from datetime import UTC, datetime

import pytest

from src.config import Settings
from src.domain.message import Message
from src.models import Source
from src.publisher import ensure_queue, publish_message, to_message_create


def make_message(**overrides) -> Message:
    base = {
        "id": "yt-1",
        "author": "@viewer",
        "author_id": "UCabc",
        "text": "hello",
        "timestamp": datetime.now(UTC),
        "platform": "youtube",
        "stream_id": "VID1",
    }
    base.update(overrides)
    return Message(**base)


class FakeBroker:
    """Duck-typed RabbitBroker stand-in recording publish/declare calls."""

    def __init__(self) -> None:
        self.published: list[tuple[dict, str]] = []
        self.declared: list = []

    async def publish(self, message, *, queue=None) -> None:
        self.published.append((message, queue))

    async def declare_queue(self, queue) -> None:
        self.declared.append(queue)


def test_to_message_create_maps_fields():
    create = to_message_create(make_message(), "@channel")

    assert create.body == "hello"
    assert create.source == Source.YOUTUBE
    assert create.message_id == "yt-1"
    assert create.author_id == "UCabc"
    assert create.stream_id == "VID1"
    assert create.channel_id == "channel"


def test_to_message_create_author_id_falls_back_to_author():
    create = to_message_create(make_message(author_id=""), "channel")
    assert create.author_id == "@viewer"


@pytest.mark.asyncio
async def test_publish_message_publishes_json_payload_to_queue():
    broker = FakeBroker()
    settings = Settings(youtube_channel="channel")

    await publish_message(broker, make_message(), settings)

    assert len(broker.published) == 1
    payload, queue = broker.published[0]
    assert queue == "messages"
    assert payload == {
        "body": "hello",
        "source": 1,
        "message_id": "yt-1",
        "author_id": "UCabc",
        "stream_id": "VID1",
        "channel_id": "channel",
    }


@pytest.mark.asyncio
async def test_ensure_queue_declares_durable_messages_queue():
    broker = FakeBroker()
    settings = Settings()

    await ensure_queue(broker, settings)

    assert len(broker.declared) == 1
    queue = broker.declared[0]
    assert queue.name == "messages"
    assert queue.durable is True
