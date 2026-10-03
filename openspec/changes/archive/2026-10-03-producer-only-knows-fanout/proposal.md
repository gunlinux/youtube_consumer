## Why

The producer currently declares the consumer's durable queue and its binding at
startup, so it still hard-codes knowledge of the consumer's topology. A pure
producer should only need to know the fanout exchange it publishes to; queues
and bindings belong to the consumers that own them.

## What Changes

- **BREAKING** (topology ownership): stop declaring the durable `messages` queue
  and the exchange→queue binding from the producer. The producer declares only
  the fanout exchange it publishes to; consumers are responsible for declaring
  their own durable queues and bindings.
- Remove the `amqp_queue` setting from `Settings` and `.env.example`; the
  producer no longer has a queue to name. `amqp_exchange` (default `messages`)
  remains.
- Rename `ensure_topology` to `ensure_exchange` (or equivalent) so it declares
  only the fanout exchange before the first publish. Publishing to the exchange
  is unchanged.
- The "publishes are never silently dropped" guarantee moves to the consumer:
  `stream_stats_consumer` must declare its durable queue and bind it to the
  exchange before the producer starts (or before it needs the messages).

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `message-publishing`: the "Exchange, queue, and binding are declared before
  publishing" requirement is replaced by an exchange-only declaration
  requirement, and the producer no longer has or uses a queue setting.

## Impact

- Affected code: `src/publisher.py` (`ensure_topology` → exchange-only
  declaration; drop the queue declaration and binding), `src/config.py` (remove
  `amqp_queue`), `src/__main__.py` (call the renamed function), `.env.example`,
  `README.md`, `AGENTS.md`, and `test/test_publish.py` (assert only
  `declare_exchange`, no queue/binding; drop `amqp_queue` usage).
- No change to `MessageCreate`, `Source`, the published payload JSON, the
  exchange name default, CLI, or logs.
- Deployment note: the consumer must own the queue/binding. Any deployment that
  relied on this producer to create the `messages` queue and binding must ensure
  `stream_stats_consumer` (or another owner) declares them, or messages
  published before a binding exists will be dropped by the fanout exchange.
