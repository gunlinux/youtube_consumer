## 1. Configuration

- [x] 1.1 In `src/config.py` add an `amqp_exchange: str = "messages"` setting
      alongside `amqp_queue`, keeping `amqp_queue` as the bound queue name.
      Verify with `make types` (the setting is typed and imported).

## 2. Publisher topology

- [x] 2.1 In `src/publisher.py` replace `ensure_queue` with `ensure_topology`,
      which declares a durable fanout exchange (name from
      `settings.amqp_exchange`), the durable queue (`settings.amqp_queue`), and
      the binding between them, before any publish. Update the `__main__.py`
      call site and import. Verify with the tests in 3.1.
- [x] 2.2 Change `publish_message` to publish to the exchange
      (`broker.publish(payload, exchange=...)`) with no queue destination and no
      routing key, leaving `to_message_create` and the payload unchanged. Verify
      with the tests in 3.2 and 3.3.

## 3. Tests

- [x] 3.1 Extend `FakeBroker` in `test/test_publish.py` to record
      `declare_exchange` and `queue_bind`, and rewrite the queue-declaration
      test as `test_ensure_topology_declares_exchange_queue_and_binding`
      asserting a durable fanout exchange, the durable `messages` queue, and a
      binding from the exchange to the queue. Verify with `make test`.
- [x] 3.2 Rewrite `test_publish_message_publishes_json_payload_to_queue` to
      assert the publish destination is the exchange and that no queue is set as
      the destination. Verify with `make test`.
- [x] 3.3 Add a test that `publish_message` still emits the exact
      `MessageCreate` JSON (`body`, `source`, `message_id`, `author_id`,
      `stream_id`, `channel_id`) unchanged by the fanout switch. Verify with
      `make test`.

## 4. Documentation and verification

- [x] 4.1 Update `AGENTS.md`: the data-flow diagram and "Queue Contract" section
      must describe publishing to the fanout exchange, and the note about
      `ensure_queue` must be replaced by `ensure_topology`. Verify the
      description matches the implemented behavior.
- [x] 4.2 Update `README.md` if it documents the queue/publish topology, so it
      names the exchange and the declared binding; verify it matches the code.
- [x] 4.3 Run the standing checks `make check` (lint, types, tests) and confirm
      all pass.

<!-- Cross-repo follow-ups (not tasks in this repo): mirror 2.1/2.2 in
     ../twitch_consumer, and make ../stream_stats_consumer bind its durable
     queue to the exchange. Track them in their own repos before rollout. -->
