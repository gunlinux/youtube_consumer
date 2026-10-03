from datetime import UTC, datetime

import pytest
from faststream.rabbit import ExchangeType

from src.config import Settings
from src.domain.message import Message
from src.models import Source
from src.publisher import ensure_exchange, publish_message, to_message_create


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
    """Duck-typed RabbitBroker stand-in recording declare/publish calls."""

    def __init__(self) -> None:
        self.published: list[tuple] = []
        self.declared_exchanges: list = []

    async def publish(self, message, queue="", exchange=None, *, routing_key="", **kw):
        self.published.append((message, queue, exchange, routing_key))

    async def declare_exchange(self, exchange):
        self.declared_exchanges.append(exchange)
        return exchange


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
async def test_ensure_exchange_declares_only_the_exchange():
    broker = FakeBroker()
    settings = Settings()

    await ensure_exchange(broker, settings)

    assert len(broker.declared_exchanges) == 1
    exchange = broker.declared_exchanges[0]
    assert exchange.name == "messages"
    assert exchange.type == ExchangeType.FANOUT
    assert exchange.durable is True
    assert not hasattr(broker, "declared_queues")
    assert not hasattr(broker, "bound")


@pytest.mark.asyncio
async def test_ensure_exchange_honors_configured_name():
    broker = FakeBroker()
    settings = Settings(amqp_exchange="ex1")

    await ensure_exchange(broker, settings)

    assert broker.declared_exchanges[0].name == "ex1"


@pytest.mark.asyncio
async def test_publish_message_publishes_to_exchange_not_queue():
    broker = FakeBroker()
    settings = Settings(youtube_channel="channel")

    await publish_message(broker, make_message(), settings)

    assert len(broker.published) == 1
    _payload, queue, exchange, _routing_key = broker.published[0]
    assert not queue
    assert exchange.name == "messages"
    assert exchange.type == ExchangeType.FANOUT


@pytest.mark.asyncio
async def test_publish_message_payload_is_unchanged():
    broker = FakeBroker()
    settings = Settings(youtube_channel="channel")

    await publish_message(broker, make_message(), settings)

    payload, *_ = broker.published[0]
    assert payload == {
        "body": "hello",
        "source": 1,
        "message_id": "yt-1",
        "author_id": "UCabc",
        "stream_id": "VID1",
        "channel_id": "channel",
    }
