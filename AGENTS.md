# AGENTS.md

Instructional context for agents working in this repository.

## Project Overview

`youtube_consumer` is a Python 3.12 async service that polls YouTube live chat
and publishes each chat message as JSON to a RabbitMQ `fanout` exchange
(`messages`), which is bound to the durable `messages` queue, feeding the
downstream `stream_stats_consumer` → `stream_stats` (PostgreSQL) pipeline.

Data flow:

```
[YouTube live chat]
    │
    ▼
YouTubeProvider  (native poller extracted from termchat, GPL-3.0-or-later)
    │  Message dataclass (platform="youtube" | "system")
    ▼
publisher.publish_message  →  MessageCreate JSON (source=1, youtube)
    ▼
RabbitMQ "messages" fanout exchange  (durable, declared on startup)
    │  binding: fanout → "messages" queue
    ▼
RabbitMQ "messages" queue  (durable, declared on startup)
```

The YouTube poller (ytcfg/ytInitialData bootstrap, continuation polling,
reconnect/backoff) was extracted from [`termchat`](../termchat) — do not
reintroduce emote tokenization or TUI rendering. Two fields were added on top
of termchat so messages map onto the `stream_stats` schema: `author_id`
(`authorExternalChannelId`) and `stream_id` (resolved live video id).

## Key Components

- `src/__main__.py` — entry point (`python -m src`). CLI arg parsing
  (`--channel`), SIGINT/SIGTERM handling, main loop: broker start →
  `ensure_topology` → iterate `provider.messages()` → publish. System messages
  are logged (warning), never published.
- `src/config.py` — `Settings` (pydantic-settings), env-loaded with `env_prefix=""`
  from `.env`. Fields: `youtube_channel`, `amqp_dsn`, `amqp_queue`,
  `amqp_exchange`, `amqp_reconnect_delay`.
- `src/models.py` — `Source` IntEnum (`TWITCH=0`, `YOUTUBE=1`) and
  `MessageCreate` pydantic model: the exact queue payload contract shared with
  `stream_stats_consumer`. `source` is always `1`.
- `src/publisher.py` — FastStream `RabbitBroker` factory, `make_exchange`
  (durable `fanout` `RabbitExchange`), `ensure_topology` (declares the exchange,
  the durable queue, and the binding between them, so publishes are never
  silently dropped), `to_message_create` (Message → MessageCreate mapping),
  `publish_message` (publishes to the exchange, no queue target).
- `src/domain/message.py` — frozen `Message` dataclass
  (`id, author, author_id, text, timestamp, platform, stream_id`) plus
  `Message.system(text)` factory for provider error/status messages.
- `src/domain/provider.py` — `Provider` protocol: `messages() ->
  AsyncGenerator[Message, None]`.
- `src/providers/youtube.py` — `YouTubeProvider`: resolves the live watch URL
  (`@channel/live` → `watch?v=`), then runs `_YouTubeLiveChatPoller` in a
  `ThreadPoolExecutor` (max 1) and yields `Message` objects. Internals:
  `_extract_bootstrap` (regex-parse `ytcfg` + `ytInitialData`, pull
  `liveChatRenderer` continuation), `_extract_continuation`, `_map_entry`,
  `_renderer_to_entry` (text + paid `[SC <amount>]` messages), `_runs_to_text`
  (flattens emoji runs to `:shortcut:` text), `_iter_action_entries`
  (unwraps `replayChatItemAction`).

## Building and Running

Managed with `uv` (Python 3.12; see `.python-version`).

```bash
uv sync --dev        # install deps (dev group)
cp .env.example .env # set youtube_channel, amqp_dsn

uv run python -m src --channel <channel>
uv run python -m src                    # channel from YOUTUBE_CHANNEL env / .env
```

RabbitMQ is provided by `../rabbit/run.sh`. Exit via Ctrl+C / SIGTERM.

Docker (two-stage build, uv installs into `/app/.venv`):

```bash
docker build -t youtube_consumer .
docker run --env-file .env youtube_consumer
```

## Testing

```bash
make test     # uv run pytest
```

Tests live in `test/` and are configured via `[tool.pytest.ini_options]` in
`pyproject.toml` (`--strict-markers`, `--strict-config`, verbose).

Conventions:
- Async tests are marked `@pytest.mark.asyncio`.
- The RabbitMQ broker is **never** touched in tests. `test/test_publish.py`
  uses a duck-typed `FakeBroker` (records `publish`, `declare_exchange`,
  `declare_queue`, and queue-binding calls) and plain `Settings(...)` instances.
- The YouTube poller is tested with hand-built fakes (`_FakeClient`,
  `_FakeResponse`) satisfying the `_HTTPClient` protocol; provider-level tests
  use `unittest.mock.patch.object` on `_open_chat`.
- Provider internals are tested directly via private imports
  (`from src.providers.youtube import _extract_bootstrap, ...`).
- Fixtures like `_innertube_action_response` build realistic
  `continuationContents.liveChatContinuation` payloads.

## Development Conventions

```bash
make check   # lint + types + test (default verification gate)
make lint    # ruff check . && flake8 src/ test/
make types   # mypy src/ (strict)
make fix     # ruff check --fix && ruff format
```

Code style:
- 88-column limit (ruff + flake8 `max-line-length = 88`, E203 ignored;
  isort `profile = "black"`, `known_first_party = ["src"]`).
- Full type annotations required — mypy runs with `disallow_untyped_defs`,
  `disallow_incomplete_defs`, `disallow_untyped_decorators`,
  `warn_return_any`, `strict_equality`, etc. `src/providers/youtube.py` is
  fully typed.
- Module docstrings on the main modules (`publisher.py`, `providers/youtube.py`).
- Private helpers are underscore-prefixed (`_map_entry`, `_runs_to_text`, …).
- Channel handles are normalized with `.lstrip("@")` at the entry point and in
  `YouTubeProvider.__init__` / `to_message_create` — keep this invariant.
- The project is `[tool.uv] package = false`: run as a module
  (`python -m src`), never `pip install`-ed.
- Known deliberate lint ignores (keep documented):
  - `BLE001` — blind `except Exception` in the reconnect loop / health checks.
  - `TRY002` — bare `raise` in the poller retry path.
  Both are in `[tool.ruff.lint] ignore`; do not "fix" them silently.

## Queue Contract

Published payload (identical to what `stream_stats_consumer` validates):

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

- `author_id` falls back to `author` when `authorExternalChannelId` is empty
  (`to_message_create`).
- `channel_id` is the channel handle with `@` stripped.
- `Message.platform == "system"` messages are logged, not published.
- Transport: messages are published to the durable `fanout` exchange named by
  `amqp_exchange` (default `messages`), with no routing key. On startup
  `ensure_topology` declares the exchange, the durable `messages` queue
  (`amqp_queue`), and the binding between them; the fanout has no bound queue it
  would drop messages, so the binding must exist before the first publish.
  `stream_stats_consumer` must bind its queue to the same exchange; a matching
  `topic`/filtering scheme is deliberately not used.

## Gotchas

- The poller is synchronous and blocking (urllib/httpx sync client, sleeps in
  0.1s slices against a `threading.Event`); it is bridged to async via
  `run_in_executor` with a single-worker `ThreadPoolExecutor`. Preserve this
  bridge when changing the provider.
- Not-live channels: no active stream (HTTP 400 from the chat API) or a
  missing `liveChatRenderer` (`_YouTubeBootstrapError`) is treated as "not
  live" — the provider emits a system message, waits an idle gap, and keeps
  retrying instead of exiting. The gap starts at `_IDLE_BACKOFF_MIN_S` (1s) and
  doubles per consecutive not-live result up to `_IDLE_BACKOFF_MAX_S` (60s);
  it resets to 1s after the first successful poller step of a live chat. A
  clean chat end (`_next_or_none` returns `None`) also reconnects with the same
  backoff. Non-offline failures still terminate the provider with a system
  message.
- `_extract_continuation` clamps poll sleep to `[1.0, 10.0]`s based on
  `timeoutMs` (default 2.0s).
- `_post_chat` retries 429/5xx with exponential backoff (max 3 retries); do
  not break the `resp.raise_for_status()` ordering.
- Timestamps: microseconds since epoch (`timestampUsec`) converted to tz-aware
  UTC `datetime`; messages older than provider startup (`startup_time`) are
  skipped.
