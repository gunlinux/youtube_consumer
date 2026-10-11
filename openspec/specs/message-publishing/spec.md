## Purpose

Defines how the YouTube chat producer delivers messages to RabbitMQ: chat
messages are published to a shared fanout exchange so that consumers can attach
their own queues without the producer knowing them.

## Requirements

### Requirement: Chat messages are published to a fanout exchange

The producer SHALL publish each chat message to a fanout exchange rather than
directly to a named queue. The exchange name SHALL be configurable, defaulting
to `messages`. The message body SHALL remain the same `MessageCreate` JSON
payload published today (a fanout exchange has no routing key).

#### Scenario: Message is published to the exchange

- **WHEN** a valid chat message is published
- **THEN** a `basic.publish` is sent to the configured fanout exchange
- **AND** no queue name is set as the publish routing destination by the
  producer

#### Scenario: Exchange name is configurable

- **WHEN** the producer starts with an exchange name configured
- **THEN** it publishes to that exchange

#### Scenario: Payload is unchanged

- **WHEN** any chat message is published
- **THEN** the body is the same `MessageCreate` JSON (`body`, `source`,
  `message_id`, `author_id`, `author`, `stream_id`, `channel_id`) sent before
  this change, where `author` is the chatter's display name and `author_id` its
  platform id

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
