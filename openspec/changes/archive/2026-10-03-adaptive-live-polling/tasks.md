## 1. Provider retry logic

- [x] 1.1 In `src/providers/youtube.py` add idle-backoff bounds
      (`_IDLE_BACKOFF_MIN_S = 1.0`, `_IDLE_BACKOFF_MAX_S = 60.0`), remove
      `_RECONNECT_SLEEP_S`, and widen the offline classifier so
      `_YouTubeBootstrapError` is treated as a "not live" (retryable) condition
      alongside HTTP 400. Verify with `make types` and existing provider tests.
- [x] 1.2 In `YouTubeProvider.messages()` replace the two fixed
      `_RECONNECT_SLEEP_S` waits with a single backoff counter that starts at
      the minimum, doubles per consecutive "not live" result, clamps at the
      maximum, and resets to the minimum after the first successful
      `_next_or_none(chat)` step; keep emitting a system message per failed
      check and keep the provider running. Verify with the tests in task 2.1.

## 2. Tests

- [x] 2.1 Add provider-level tests (in `test/providers/test_youtube.py`) using
      `unittest.mock.patch.object` on `_open_chat` / a fake poller that assert
      the idle gap sequence is 1s, 2s, 4s, … capped at 60s and resets to 1s
      after a live chat opens. Verify with `make test`.
- [x] 2.2 Add a test that a `_YouTubeBootstrapError` from the poller keeps the
      provider alive (another retry happens, no exit) and still emits a system
      message. Verify with `make test`.
- [x] 2.3 Confirm the existing in-stream cadence coverage in
      `test/providers/test_youtube.py` (1/10s clamps, 2s default) still passes
      unchanged. Verify with `make test`.

## 3. Documentation and verification

- [x] 3.1 Update the `AGENTS.md` "Offline channels" gotcha to describe the
      exponential idle backoff (1s→60s) and that bootstrap failures count as
      not-live; verify the description matches the implemented behavior.
- [x] 3.2 Run the standing checks `make check` (lint, types, tests) and confirm
      all pass.
