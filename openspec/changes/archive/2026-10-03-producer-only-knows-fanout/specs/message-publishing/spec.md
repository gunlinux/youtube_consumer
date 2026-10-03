## ADDED Requirements

### Requirement: Only the fanout exchange is declared before publishing

The producer SHALL declare the fanout exchange before it publishes anything. The
producer SHALL NOT declare or bind any queue: queues and their bindings belong
to the consumers that own them, and the producer SHALL have no queue setting.
Exchange declaration SHALL be idempotent and SHALL run on every startup.
Because a fanout exchange drops a message with no bound queue, ensuring a
durable queue is bound before messages are published is the responsibility of
the consumer, not the producer.

#### Scenario: Exchange is declared before the first publish

- **WHEN** the producer starts successfully
- **THEN** the fanout exchange is declared before any message is published

#### Scenario: Producer declares no queue or binding

- **WHEN** the producer starts successfully
- **THEN** it declares the fanout exchange only
- **AND** it declares and binds no queue

#### Scenario: Startup is idempotent

- **WHEN** the producer restarts against a broker that already has the exchange
- **THEN** startup succeeds without error and unchanged topology is preserved

#### Scenario: No queue setting is required

- **WHEN** the producer is configured with only an exchange name and no queue
  name
- **THEN** it starts and publishes normally

## REMOVED Requirements

### Requirement: Exchange, queue, and binding are declared before publishing

**Reason**: The producer no longer owns the consumer's queue topology. Declaring
the durable queue and its binding from the producer hard-codes knowledge of a
consumer that the producer should not have; that declaration moves to the
consumer.

**Migration**: Queue and binding declaration moves to the consumer
(`stream_stats_consumer`). The producer now declares only the fanout exchange
(see the added requirement above). A deployment must ensure a durable queue is
bound to the exchange before producers publish; otherwise a fanout exchange
drops messages with no bound queue.
