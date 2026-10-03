## Context

See proposal.md - Why. Today `ensure_topology` declares the exchange, the
durable `messages` queue, and the binding, so the producer carries the
consumer's topology. `Settings` exposes both `amqp_exchange` and `amqp_queue`.
Publishing already targets the exchange with no routing key and is unaffected.

## Goals / Non-Goals

**Goals:**
- Producer declares only the fanout exchange it publishes to.
- Remove queue knowledge (`amqp_queue`) from the producer's config and code.

**Non-Goals:**
- Changing the fanout exchange name, the `MessageCreate` payload, or the
  publish call.
- Moving/renaming the capability or the exchange.
- Changing `youtube-live-polling`.

## Decisions

### Keep declaring the exchange, drop the queue and binding

`ensure_topology` becomes an exchange-only declaration (e.g.
`ensure_exchange`). Rationale: `broker.publish(exchange=...)` requires the
exchange to exist, so the producer must know and be able to declare the
exchange; but queues and bindings are owned by consumers. Alternative
considered: don't declare anything and rely on broker-side provisioning — this
breaks the "start against a fresh broker" path without adding value.

### Remove `amqp_queue` rather than keep it unused

Removing the setting keeps config honest about what the producer knows. Pydantic
`BaseSettings` ignores unknown env vars, so a stale `amqp_queue` in an existing
`.env` will not fail startup. Alternative considered: keep `amqp_queue` for
compatibility — rejected as dead configuration that implies ownership the
producer no longer has.

### The never-silently-dropped guarantee moves to the consumer

The producer can no longer guarantee a bound queue exists. `stream_stats_consumer`
must declare its durable queue and bind it to the exchange. This is a contract
change, not a code change in this repo.

## Risks / Trade-offs

- [Messages published before any consumer binds a queue are dropped by the
  fanout exchange] → The consumer must declare and bind before the producer
  starts; document this in README/AGENTS and call it out in the deploy step.
- [Existing deployments that relied on this producer to create the `messages`
  queue] → Ensure `stream_stats_consumer` owns the queue/binding; verify the
  queue exists after rollout.

## Migration Plan

1. Land the consumer-side queue/binding ownership first (or in the same deploy)
   so a durable queue is bound before producers drop queue creation.
2. Deploy this producer change; on startup it declares only the exchange.
3. Verify: publish a message, confirm it is retained in the consumer's durable
   queue.
4. Rollback: revert this producer change; the old `ensure_topology` recreates the
   queue/binding (idempotent), so no broker cleanup is required.
