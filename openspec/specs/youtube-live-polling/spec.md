## Purpose

Defines how the YouTube provider paces its requests to YouTube: a cheap idle
rhythm while the channel is not live, and a low-latency rhythm while live chat
is active.

## Requirements

### Requirement: Retry cadence while the channel is not live

When a check finds no active live stream or live chat, the provider SHALL treat
it as a retryable "not live" condition and SHALL NOT terminate. The gap before
the next check SHALL start at 1 second and double after each consecutive "not
live" result, capped at 60 seconds, so YouTube is polled at most once per minute
while idle.

#### Scenario: Consecutive not-live checks back off exponentially

- **WHEN** a "not live" check is followed by more "not live" checks
- **THEN** the wait before the next check is 1s, then 2s, then 4s, and so on
- **AND** the wait never exceeds 60s

#### Scenario: Offline channel does not stop the provider

- **WHEN** the channel is not live and every check reports no active stream or
  live chat
- **THEN** the provider emits a system message for each failed check
- **AND** the provider keeps running and retrying instead of exiting

#### Scenario: Backoff resets after the channel goes live

- **WHEN** a live chat opens successfully after one or more "not live" checks
- **THEN** the next idle wait (if the channel goes offline again) starts again
  at 1s rather than the previous capped value

### Requirement: Active live chat poll cadence

While live chat is active, the provider SHALL pace continuation requests using
the `timeoutMs` hint returned by YouTube, clamped to the range 1 to 10 seconds,
and SHALL use 2 seconds when no hint is provided. This cadence SHALL be used
instead of the idle backoff whenever chat is live.

#### Scenario: Hint within range is honored

- **WHEN** a continuation response carries a `timeoutMs` hint between 1000 and
  10000
- **THEN** the provider waits that duration before the next continuation request

#### Scenario: Hint is clamped

- **WHEN** a continuation response carries a `timeoutMs` hint below 1000 or
  above 10000
- **THEN** the provider waits 1s or 10s respectively

#### Scenario: Missing hint falls back to the default

- **WHEN** a continuation response carries no `timeoutMs` hint
- **THEN** the provider waits 2 seconds before the next continuation request
