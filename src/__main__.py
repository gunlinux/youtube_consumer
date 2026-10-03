import argparse
import asyncio
import logging
import signal

from src.config import Settings
from src.providers.youtube import YouTubeProvider
from src.publisher import ensure_exchange, make_broker, publish_message

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube_consumer",
        description="Publish YouTube live chat messages to the RabbitMQ messages queue",
    )
    parser.add_argument(
        "--channel",
        help="YouTube channel handle (without @); falls back to YOUTUBE_CHANNEL env",
    )
    return parser


async def run(settings: Settings, channel: str) -> None:
    broker = make_broker(settings)
    await broker.start()
    try:
        await ensure_exchange(broker, settings)
        provider = YouTubeProvider(channel)

        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        async for msg in provider.messages():
            if stop.is_set():
                break
            if msg.platform == "system":
                logger.warning("%s", msg.text)
                continue
            await publish_message(broker, msg, settings)
    finally:
        await broker.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings()
    channel = (args.channel or settings.youtube_channel).lstrip("@")
    if not channel:
        parser.error("--channel is required (or set YOUTUBE_CHANNEL in .env)")
    try:
        asyncio.run(run(settings, channel))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
