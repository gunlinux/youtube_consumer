## Purpose

Defines how the YouTube chat producer delivers messages to RabbitMQ: chat
messages are published to a shared fanout exchange so that consumers can attach
their own queues without the producer knowing them.

## ADDED Requirements

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
  `message_id`, `author_id`, `stream_id`, `channel_id`) sent before this change

### Requirement: Exchange, queue, and binding are declared before publishing

The producer SHALL declare the fanout exchange, the durable queue, and the
binding that routes the exchange to that queue before it publishes anything, so
that a subscriber which has not yet started cannot cause messages to be silently
dropped. Declaration SHALL be idempotent and SHALL run on every startup.

#### Scenario: Topology is declared before the first publish

- **WHEN** the producer starts successfully
- **THEN** the fanout exchange, the durable queue, and the binding are declared
  before any message is published

#### Scenario: No subscriber is bound yet

- **WHEN** the only binding is the one the producer declares
- **THEN** published messages are retained in the durable queue for the
  subscriber to consume later, rather than being dropped

#### Scenario: Startup is idempotent

- **WHEN** the producer restarts against a broker that already has the exchange,
  queue, and binding
- **THEN** startup succeeds without error and unchanged topology is preserved
