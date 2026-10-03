## Context

See `proposal.md` - Why. Today `src/publisher.py` does two things at startup:
`make_broker` builds a `RabbitBroker`, and `ensure_queue` declares the durable
queue named by `settings.amqp_queue` (default `messages`). `publish_message`
then calls `broker.publish(payload, queue=settings.amqp_queue)`. The same shape
exists in `../twitch_consumer`, and `../stream_stats_consumer` subscribes with
`RabbitQueue(settings.amqp_queue, durable=True)`. `src/config.py` exposes
`amqp_queue` and `amqp_reconnect_delay` but no exchange setting.

Constraints that shape the design:
- The payload contract (`MessageCreate`, `Source.YOUTUBE == 1`) is fixed and
  shared with the consumer; it must not change.
- FastStream's `broker.publish` accepts either a `queue=` or an `exchange=`
  destination; using `exchange=` is the supported way to publish to a fanout.
- The consumer must bind its own queue to the exchange for delivery to happen;
  with a fanout exchange the producer cannot route to a queue that is not bound.

## Goals / Non-Goals

**Goals:**
- Publish to a fanout exchange while keeping the current payload byte-for-byte
  compatible.
- Keep the "never silently dropped" guarantee by declaring the exchange, queue,
  and binding before the first publish.
- Keep the change to this repo minimal and mirrored in the sibling repos.

**Non-Goals:**
- Adding routing-key-based filtering (that would be a `topic`/`direct` exchange;
  explicitly not fanout).
- Adding a second consumer now; the driver is decoupling, not a new subscriber.
- Changing the queue name used by `stream_stats_consumer` (`messages` stays the
  bound queue name).

## Decisions

### One `fanout` exchange named by a new `amqp_exchange` setting

Add `amqp_exchange: str = "messages"` to `Settings`. The default matches the
current queue name so the deployment story is unchanged and operators can point
the exchange elsewhere. Publishing uses
`broker.publish(payload, exchange=RabbitExchange(settings.amqp_exchange))`.

*Alternative considered:* a hard-coded exchange name. Rejected — the config
already parameterizes the queue, so the exchange should be symmetric.

*Alternative considered:* a `topic` exchange with a `source`/`channel` routing
key. Rejected — the user chose plain fanout; no server-side filtering is needed
yet, and adding it now is speculative.

### `ensure_queue` becomes `ensure_topology` and declares exchange + queue + binding

Startup declares, in order: the durable fanout exchange, the durable queue, and
the binding. This keeps responsibility with the producer: it can declare
everything before publishing, so a message published while the consumer is down
still lands in the durable queue and is delivered when the consumer binds.
Binding a queue the producer does not own is deliberate here — it is the price
of the never-silently-dropped guarantee under "producers declare the binding".

*Alternative considered:* the producer declares only the exchange and the
consumer declares and binds its own queue. Rejected (user decision) — it moves
the drop-safety requirement onto the consumer and reintroduces the coupling the
change is meant to remove, in the opposite direction.

*Alternative considered:* keep the function name `ensure_queue` and add
declarations. Rejected — the name would understate what it now does; the tests
and call site are small.

### Fanout means no routing key

Under fanout the broker ignores routing keys, so `publish_message` passes no
`routing_key`. The payload therefore needs no `source`/`channel` routing
prefixes, and `to_message_create` is untouched.

## Risks / Trade-offs

- [Rollout ordering: an old consumer bound only to the plain queue receives
  nothing once the producer publishes to the exchange] → the producer declares
  the exchange, queue, and binding on startup, so the queue is still fed; the
  consumer must be updated to bind the exchange, and all three services ship
  together. Documented in the proposal's deployment note.
- [A fanout exchange with no bound queue drops messages] → mitigated by the
  producer declaring the binding before publishing (see spec).
- [Duplicated declaration of the same exchange/queue/binding across producer and
  future consumers] → declarations are idempotent; identical parameters are
  required, so the exchange/queue names and `durable` flags are centralized in
  config per service and must match.
- [Unbounded fan-out if many queues are later bound] → each queue gets its own
  copy; that is the intended semantics and is bounded by the operator adding
  bindings.

## Migration Plan

1. Land the change in `youtube_consumer` (exchange/queue/binding declared,
   publish to exchange) and the mirrored change in `twitch_consumer`.
2. Update `stream_stats_consumer` to bind its durable queue to the exchange at
   subscription time.
3. Rollback: revert the producers to `queue=` publishing; the queue, exchange,
   and binding may remain declared, so rollback needs no broker cleanup.

## Open Questions

- None. The sibling-repo edits are tracked as follow-up work outside this
  repo's OpenSpec change; their content mirrors decision 2 above.
