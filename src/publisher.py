"""FastStream (RabbitMQ) publisher for YouTube chat messages."""

import logging

from faststream.rabbit import RabbitBroker, RabbitQueue

from src.config import Settings
from src.domain.message import Message
from src.models import MessageCreate, Source

logger = logging.getLogger(__name__)


def make_broker(settings: Settings) -> RabbitBroker:
    """Build the RabbitMQ broker, mirroring stream_stats_consumer conventions."""
    return RabbitBroker(
        url=str(settings.amqp_dsn),
        reconnect_interval=settings.amqp_reconnect_delay,
        logger=logger,
    )


async def ensure_queue(broker: RabbitBroker, settings: Settings) -> None:
    """Declare the durable queue so publishes are never silently dropped."""
    await broker.declare_queue(RabbitQueue(settings.amqp_queue, durable=True))


def to_message_create(message: Message, channel: str) -> MessageCreate:
    """Map a chat Message onto the stream_stats queue payload schema."""
    return MessageCreate(
        body=message.text,
        source=Source.YOUTUBE,
        message_id=message.id,
        author_id=message.author_id or message.author,
        stream_id=message.stream_id,
        channel_id=channel.lstrip("@"),
    )


async def publish_message(
    broker: RabbitBroker, message: Message, settings: Settings
) -> None:
    """Publish one chat message to the messages queue as JSON."""
    payload = to_message_create(message, settings.youtube_channel)
    await broker.publish(payload.model_dump(mode="json"), queue=settings.amqp_queue)
    logger.info("Published %s from %s", payload.message_id, payload.author_id)
