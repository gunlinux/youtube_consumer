## Context

See `proposal.md` - Why. The provider's retry loop lives in
`YouTubeProvider.messages()` (async) and drives a synchronous
`_YouTubeLiveChatPoller` through a single-worker executor. Two failure sites
currently share a fixed `_RECONNECT_SLEEP_S = 30.0` wait:

1. Opening the chat - `_open_chat` / `_resolve_video_url` or the first poller
   step failing.
2. A poller step during iteration returning HTTP 400 ("no active stream").

Only `httpx.HTTPStatusError` with status 400 is classified as offline
(`_is_offline_error`). A `_YouTubeBootstrapError` (no `liveChatRenderer`, e.g.
`@channel/live` resolving to a non-live page) is treated as fatal and makes the
provider exit. The in-stream cadence comes from the poller:
`_extract_continuation` clamps YouTube's `timeoutMs` to `[1.0, 10.0]`s
(default 2.0s).

## Goals / Non-Goals

**Goals:**
- Keep the provider alive across an offline channel.
- Cap idle request pressure at one check per minute.
- Leave the live cadence untouched.

**Non-Goals:**
- Making the idle wait interruptible by SIGTERM (today's fixed 30s wait is not
  either; shutdown latency is unchanged in kind).
- Introducing jitter, config/env knobs, or per-status-code backoff policies.
- Changing the queue payload, `MessageCreate`, config, or CLI.

## Decisions

### Backoff state lives in `YouTubeProvider.messages()`

The wait must survive across both failure sites and be reset when live chat
resumes, so the counter is a local in the provider's outer `while True` loop
rather than a poller field. The poller stays unchanged: it still reports
failures, the provider decides how long to wait.

*Alternative considered:* put the backoff inside `_YouTubeLiveChatPoller`.
Rejected - the poller is re-created on every reconnect, so the counter would
reset each time and could never grow.

### A helper computes the wait, then doubles

An idle-gap helper holds `_IDLE_BACKOFF_MIN_S = 1.0` and
`_IDLE_BACKOFF_MAX_S = 60.0`. Each "not live" result uses the current gap and
doubles it, clamped to the max; a successful live-chat open sets the gap back to
the minimum. `_RECONNECT_SLEEP_S` is removed.

### `_YouTubeBootstrapError` counts as "not live"

When the channel is offline, `@channel/live` resolves to a page without a
`liveChatRenderer`, so `_extract_bootstrap` raises `_YouTubeBootstrapError`.
That is exactly the "no active live stream" case the change targets, so the
offline classifier is widened to include it; the provider backs off instead of
exiting. Genuinely unexpected errors keep today's behavior and terminate.

*Alternative considered:* match on the error message text. Rejected as brittle.

### Reset on the first successful poller step

Resetting after `_open_chat` returns is wrong: the iterator is lazy and has not
fetched anything yet. The provider resets the gap after the first
`_next_or_none(chat)` call in the inner loop that does not raise a "not live"
error, which is the first point we know chat is genuinely live.

## Risks / Trade-offs

- [A short live stream ending right after a reset back off from 1s again] →
  acceptable: the ramp to 60s is quick (6 steps) and correctness is unaffected.
- [Widening the offline classifier could treat a real HTML/API break as
  "offline" and retry forever instead of exiting] → retries are capped at one
  per minute and emit a system message each time, so the condition stays visible
  in logs rather than failing silently.
- [Idle wait blocks the async generator for up to 60s during shutdown] → same
  class of latency as today's 30s fixed wait; out of scope per Non-Goals.
