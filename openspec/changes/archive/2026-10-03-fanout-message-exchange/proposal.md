## Why

Both chat producers (`twitch_consumer`, `youtube_consumer`) publish directly to
the single durable `messages` queue, so every producer must know the consumer's
queue name and any second consumer would require editing every producer. Routing
chat messages through one `fanout` exchange decouples publishing from consuming
and lets additional consumers be added without touching the producers.

## What Changes

- **BREAKING** (transport contract): publish chat messages to a `fanout`
  exchange instead of directly to the `messages` queue. Because a `fanout`
  exchange has no routing key, the payload and `MessageCreate` schema are
  unchanged.
- **BREAKING** (transport contract): producers declare the exchange, the durable
  `messages` queue, and the binding between them, preserving today's
  "publishes are never silently dropped" guarantee.
- Adopt the same exchange in all three services: `twitch_consumer` and
  `youtube_consumer` publish to it, `stream_stats_consumer` binds its queue to
  it. This change plans `youtube_consumer`; the sibling repos are follow-ups.
- Add an exchange-name setting (`amqp_exchange`, default `messages`) to config,
  keeping `amqp_queue` as the bound queue name.

## Capabilities

### New Capabilities

- `message-publishing`: how chat messages are published to RabbitMQ — the
  exchange/queue topology, declaration/binding responsibility, and the
  never-silently-dropped guarantee.

### Modified Capabilities

<!-- none: `youtube-live-polling` describes polling cadence and is unaffected -->

## Impact

- Affected code: `src/publisher.py` (`make_broker`/`ensure_queue` →
  declare exchange + queue + binding; `publish_message` publishes to the
  exchange), `src/config.py` (new `amqp_exchange` setting).
- Affected services (contract, tracked as follow-ups outside this repo):
  `../twitch_consumer` (same change to its publisher) and
  `../stream_stats_consumer` (its subscriber must bind the queue to the
  exchange).
- No change to `MessageCreate`, `Source`, the payload JSON, CLI, or logs.
- Tests: `test/test_publish.py` (assert `declare_exchange`, queue, and binding;
  assert publish targets the exchange).
- Deployment note: old producers publishing to the plain queue and new
  consumers binding the exchange must not run interleaved during rollout; the
  exchange/queue/binding are declared idempotently on startup.
