## 1. Publisher declares only the exchange

- [x] 1.1 In `src/publisher.py` replace `ensure_topology` with an exchange-only
      declaration (e.g. `ensure_exchange`) that declares the durable fanout
      exchange and nothing else. Verify by reading the function: no
      `declare_queue` / `bind` calls remain.
- [x] 1.2 Update `src/__main__.py` to import and call the renamed function in
      `run()`. Verify `uv run python -c "import src.__main__"` imports cleanly.

## 2. Remove queue configuration

- [x] 2.1 Remove the `amqp_queue` field from `Settings` in `src/config.py`.
      Verify `Settings(amqp_exchange="ex1")` still constructs and
      `amqp_queue` is absent.
- [x] 2.2 Remove `amqp_queue` from `.env.example` (and any Dockerfile comment
      that names it). Verify `grep -r amqp_queue src/ .env.example Dockerfile`
      returns no matches.

## 3. Tests

- [x] 3.1 Update `test/test_publish.py`: rename/replace
      `test_ensure_topology_declares_exchange_queue_and_binding` with a test
      asserting only the exchange is declared and no queue/binding is created;
      drop the `amqp_queue` usage in `test_ensure_topology_honors_configured_names`.
      Verify `make test` passes.
- [x] 3.2 Confirm the `FakeBroker` still records `declare_exchange` and that no
      test asserts a queue or binding. Verify `make test` passes.

## 4. Docs

- [x] 4.1 Update `README.md` and `AGENTS.md` to state the producer declares only
      the fanout exchange, that `amqp_queue` is gone, and that the consumer owns
      the durable queue and binding. Verify by reading both files for the queue
      ownership statement.

## 5. Verification

- [x] 5.1 Run `make check` (ruff + flake8 + mypy + pytest) and confirm it
      passes. Result: 46 passed; ruff, flake8, mypy clean.
- [x] 5.2 Confirm the consumer owns the queue/binding: `stream_stats_consumer`
      declares the durable queue and binds it to the exchange before the
      producer starts. Record where this happens (repo/file) or flag it as a
      follow-up in the sibling repo. Result: confirmed at
      `../stream_stats_consumer/src/consumer.py` — the `@broker.subscriber`
      declares the durable `RabbitQueue(settings.amqp_queue, durable=True)`
      bound to the `fanout` `RabbitExchange(settings.amqp_exchange)`, so the
      consumer owns the queue and binding.
