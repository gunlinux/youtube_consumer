## Why

When a channel is not live the provider currently hammers YouTube on a fixed
30s reconnect delay and, for some offline responses (bootstrap parse failures),
gives up entirely. That spams the API while idle and leaves the consumer dead
when the stream is simply offline. We want a cheap idle rhythm that stays alive
and an active rhythm that keeps chat latency low while live.

## What Changes

- Treat "not live" (no active stream / no live chat) as a normal, retryable
  condition: the provider stays running instead of terminating.
- Add an idle backoff: after each failed "not live" check the gap grows
  exponentially (1s → 2s → 4s … ) capped at 60s, so we check at most once per
  minute while offline.
- Reset the backoff to its minimum as soon as a live chat is successfully
  opened, so a channel coming online is picked up promptly.
- Keep the live polling cadence unchanged: use YouTube's continuation
  `timeoutMs` hint, clamped to 1–10s (default 2s).
- Replace the fixed `_RECONNECT_SLEEP_S = 30.0` reconnect delay with the
  backoff described above.

## Capabilities

### New Capabilities

- `youtube-live-polling`: polling cadence for YouTube live chat — the idle
  "not live" backoff and the active in-stream poll interval.

### Modified Capabilities

<!-- none: no existing specs in this repository -->

## Impact

- Affected code: `src/providers/youtube.py` (`YouTubeProvider.messages`,
  `_YouTubeLiveChatPoller`, `_RECONNECT_SLEEP_S`, offline/bootstrap error
  classification).
- No change to the queue contract, `MessageCreate`, config, or CLI.
- Tests: `test/providers/test_youtube.py` (backoff growth/cap/reset, offline
  stays alive).
- `AGENTS.md` gotchas describing the fixed 30s retry need updating at apply
  time.
