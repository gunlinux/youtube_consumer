# youtube_consumer

Publishes YouTube live chat messages to the RabbitMQ `messages` queue, feeding the
existing `stream_stats_consumer` → `stream_stats` storage pipeline.

```
[YouTube live chat]
    │
    ▼
youtube_consumer  (YouTubeProvider extracted from termchat)
    │  publish JSON  (MessageCreate, source=1/youtube)
    ▼
RabbitMQ "messages" queue  (durable, default exchange)
    │
    ▼
stream_stats_consumer  (FastStream, AckPolicy.MANUAL)
    │  POST /api/v1/messages  (Bearer token)
    ▼
stream_stats  (FastAPI + asyncpg)  →  PostgreSQL
```

The YouTube provider (poller, ytcfg/continuation bootstrap, reconnect/backoff) is
extracted from [termchat](../termchat) (GPL-3.0-or-later); the emote tokenization
and TUI rendering were dropped. Two fields were added so messages map onto the
`stream_stats` schema:

- `author_id` — `authorExternalChannelId` from the chat renderer
- `stream_id` — the resolved live video id (`watch?v=...`)

## Queue contract

Payload is the same `MessageCreate` JSON the `stream_stats_consumer` validates:

```json
{
  "body": "hello",
  "source": 1,
  "message_id": "yt-msg-id",
  "author_id": "UC...",
  "stream_id": "watch-video-id",
  "channel_id": "@channel"
}
```

`source` is always `1` (youtube). The durable `messages` queue is declared on
startup (matching `stream_stats_consumer`), so the producer never publishes into
a missing queue.

## Setup

```bash
uv sync --dev
cp .env.example .env   # set youtube_channel, amqp_dsn (default amqp://user:password@localhost:5672)
```

RabbitMQ is provided by `../rabbit/run.sh`; the rest of the pipeline is
`stream_stats_consumer` + `stream_stats` (see `../stream_stats/README.md`).

## Run

```bash
uv run python -m src --channel <channel>
# or
uv run python -m src   # channel from YOUTUBE_CHANNEL env / .env
```

System/error messages from the provider (`Message.system`) are logged, not
published. Exit via Ctrl+C (SIGINT) or SIGTERM.

## Development

```bash
make dev     # uv sync --dev
make check   # lint + types + test
make test
make lint
make types   # mypy
```

## Docker

```bash
docker build -t youtube_consumer .
docker run --env-file .env youtube_consumer
```
