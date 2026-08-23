import json
from unittest.mock import patch

import httpx
import pytest

from src.providers.youtube import (
    YouTubeProvider,
    _extract_bootstrap,
    _extract_continuation,
    _extract_video_id,
    _fmt_error,
    _iter_action_entries,
    _map_entry,
    _renderer_to_entry,
    _runs_to_text,
    _YouTubeBootstrapError,
    _YouTubeLiveChatPoller,
)

# --- unit tests: entry mapping ---


def test_map_entry_basic():
    entry = {
        "message_id": "abc",
        "author": {"name": "viewer1"},
        "author_id": "UC123",
        "message": "Nice stream!",
        "timestamp": 1_700_000_000_000_000,
    }
    msg = _map_entry(entry, stream_id="VIDEO1")
    assert msg is not None
    assert msg.id == "abc"
    assert msg.author == "viewer1"
    assert msg.author_id == "UC123"
    assert msg.text == "Nice stream!"
    assert msg.platform == "youtube"
    assert msg.stream_id == "VIDEO1"
    assert msg.timestamp.tzinfo is not None


def test_map_entry_author_as_string():
    entry = {"author": "viewer2", "message": "Hello"}
    msg = _map_entry(entry)
    assert msg is not None
    assert msg.author == "viewer2"
    assert msg.author_id == ""


def test_map_entry_no_text_returns_none():
    entry = {"author": "user", "message": ""}
    assert _map_entry(entry) is None


def test_map_entry_missing_id_generates_uuid():
    entry = {"author": "a", "message": "hi"}
    msg = _map_entry(entry)
    assert msg is not None
    assert len(msg.id) > 0


def test_map_entry_no_timestamp_uses_now():
    entry = {"author": "a", "message": "hi"}
    msg = _map_entry(entry)
    assert msg is not None
    assert msg.timestamp.tzinfo is not None


# --- renderer mapping ---


def test_renderer_to_entry_text_message():
    item = {
        "liveChatTextMessageRenderer": {
            "id": "Cg1",
            "message": {"runs": [{"text": "hi "}, {"text": "there"}]},
            "authorName": {"simpleText": "@viewer"},
            "authorExternalChannelId": "UCabc",
            "timestampUsec": "1700000000000000",
        }
    }
    entry = _renderer_to_entry(item)
    assert entry == {
        "message_id": "Cg1",
        "author": {"name": "@viewer"},
        "author_id": "UCabc",
        "message": "hi there",
        "timestamp": 1_700_000_000_000_000,
    }


def test_renderer_to_entry_paid_message_prefixes_amount():
    item = {
        "liveChatPaidMessageRenderer": {
            "id": "P1",
            "message": {"runs": [{"text": "thanks!"}]},
            "authorName": {"simpleText": "@fan"},
            "authorExternalChannelId": "UCfan",
            "purchaseAmountText": {"simpleText": "CHF 2.00"},
            "timestampUsec": "1700000000000000",
        }
    }
    entry = _renderer_to_entry(item)
    assert entry is not None
    assert entry["message"] == "[SC CHF 2.00] thanks!"
    assert entry["author_id"] == "UCfan"


def test_renderer_to_entry_empty_text_returns_none():
    item = {"liveChatTextMessageRenderer": {"message": {"runs": []}}}
    assert _renderer_to_entry(item) is None


def test_renderer_to_entry_skips_unknown_renderers():
    assert _renderer_to_entry({"markChatItemAsDeletedAction": {}}) is None


# --- run flattening ---


def test_runs_to_text_plain():
    assert _runs_to_text([{"text": "plain"}, {"text": " text"}]) == "plain text"


def test_runs_to_text_with_emoji():
    runs = [
        {"text": "hi "},
        {"emoji": {"shortcuts": [":smile:"], "emojiId": "U+1F600"}},
        {"text": "!"},
    ]
    assert _runs_to_text(runs) == "hi :smile:!"


def test_runs_to_text_emoji_falls_back_to_emoji_id():
    runs = [{"emoji": {"emojiId": "UCabc"}}]
    assert _runs_to_text(runs) == "UCabc"


# --- action entry iteration ---


def test_iter_action_entries_addchat_action():
    item = {
        "addChatItemAction": {
            "item": {
                "liveChatTextMessageRenderer": {
                    "id": "m1",
                    "authorName": {"simpleText": "a"},
                    "message": {"runs": [{"text": "hello"}]},
                }
            }
        }
    }
    entries = list(_iter_action_entries(item))
    assert len(entries) == 1
    assert entries[0]["message"] == "hello"


def test_iter_action_entries_unwraps_replay():
    action = {
        "replayChatItemAction": {
            "actions": [
                {
                    "addChatItemAction": {
                        "item": {
                            "liveChatTextMessageRenderer": {
                                "id": "m1",
                                "authorName": {"simpleText": "a"},
                                "message": {"runs": [{"text": "replayed"}]},
                            }
                        }
                    }
                }
            ]
        }
    }
    entries = list(_iter_action_entries(action))
    assert len(entries) == 1
    assert entries[0]["message"] == "replayed"


def test_iter_action_entries_ignores_unknown_action():
    assert list(_iter_action_entries({"markChatItemAsDeletedAction": {}})) == []


# --- bootstrap / continuation extraction ---


def _bootstrap_html(api_key="K1", continuation="CONT0"):
    ytcfg = {
        "INNERTUBE_API_KEY": api_key,
        "INNERTUBE_CONTEXT": {"client": {"clientName": "WEB", "clientVersion": "2.0"}},
    }
    yt_initial = {
        "contents": {
            "twoColumnWatchNextResults": {
                "conversationBar": {
                    "liveChatRenderer": {
                        "continuations": [
                            {
                                "invalidationContinuationData": {
                                    "continuation": continuation,
                                    "timeoutMs": 5000,
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    return (
        f"<html><script>ytcfg.set({json.dumps(ytcfg)});"
        f"var ytInitialData = {json.dumps(yt_initial)};</script></html>"
    )


def test_extract_bootstrap_happy_path():
    html = _bootstrap_html(api_key="THE_KEY", continuation="TOKEN0")
    api_key, ctx, cont = _extract_bootstrap(html)
    assert api_key == "THE_KEY"
    assert ctx["client"]["clientName"] == "WEB"
    assert cont == "TOKEN0"


def test_extract_bootstrap_accepts_reload_continuation():
    ytcfg = {"INNERTUBE_API_KEY": "K", "INNERTUBE_CONTEXT": {"client": {}}}
    yt_initial = {
        "liveChatRenderer": {
            "continuations": [{"reloadContinuationData": {"continuation": "RC1"}}]
        }
    }
    html = (
        f"<script>ytcfg.set({json.dumps(ytcfg)});"
        f"ytInitialData = {json.dumps(yt_initial)};</script>"
    )
    _, _, cont = _extract_bootstrap(html)
    assert cont == "RC1"


def test_extract_bootstrap_missing_ytcfg_raises():
    with pytest.raises(_YouTubeBootstrapError):
        _extract_bootstrap("<html>no ytcfg here</html>")


def test_extract_bootstrap_missing_api_key_raises():
    ytcfg = {"INNERTUBE_CONTEXT": {"client": {}}}
    html = f"<script>ytcfg.set({json.dumps(ytcfg)});</script>"
    with pytest.raises(_YouTubeBootstrapError):
        _extract_bootstrap(html)


def test_extract_bootstrap_missing_continuation_raises():
    ytcfg = {"INNERTUBE_API_KEY": "K", "INNERTUBE_CONTEXT": {"client": {}}}
    yt_initial = {"contents": {"foo": "bar"}}
    html = (
        f"<script>ytcfg.set({json.dumps(ytcfg)});"
        f"ytInitialData = {json.dumps(yt_initial)};</script>"
    )
    with pytest.raises(_YouTubeBootstrapError):
        _extract_bootstrap(html)


def test_extract_continuation_invalidation_variant():
    token, sleep_s = _extract_continuation(
        [{"invalidationContinuationData": {"continuation": "T1", "timeoutMs": 3000}}]
    )
    assert token == "T1"
    assert sleep_s == 3.0


def test_extract_continuation_clamps_high_timeout():
    _, sleep_s = _extract_continuation(
        [{"timedContinuationData": {"continuation": "T", "timeoutMs": 60000}}]
    )
    assert sleep_s == 10.0


def test_extract_continuation_default_sleep_when_no_timeout():
    token, sleep_s = _extract_continuation(
        [{"reloadContinuationData": {"continuation": "T"}}]
    )
    assert token == "T"
    assert sleep_s == 2.0


def test_extract_continuation_empty_returns_none():
    assert _extract_continuation([]) == (None, 0.0)


# --- video id extraction ---


def test_extract_video_id_from_watch_url():
    assert (
        _extract_video_id("https://www.youtube.com/watch?v=AbCdEfGh123")
        == "AbCdEfGh123"
    )


def test_extract_video_id_empty_without_query():
    assert _extract_video_id("https://www.youtube.com/@channel/live") == ""


# --- error formatting ---


def test_fmt_error_400_returns_human_message():
    resp = httpx.Response(400)
    err = httpx.HTTPStatusError(
        "bad request", request=httpx.Request("GET", "u"), response=resp
    )
    assert _fmt_error(err) == "no active stream (channel may be offline)"


def test_fmt_error_other_http_status_shows_code():
    resp = httpx.Response(500)
    err = httpx.HTTPStatusError(
        "oops", request=httpx.Request("GET", "u"), response=resp
    )
    assert _fmt_error(err) == "HTTP 500"


# --- poller ---


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=httpx.Request("GET", "u"),
                response=httpx.Response(self.status_code),
            )


class _FakeClient:
    def __init__(self, watch_html="", post_responses=None):
        self._watch_html = watch_html
        self._post_responses = list(post_responses or [])
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, url, **_):
        self.get_calls.append(url)
        return _FakeResponse(200, text=self._watch_html)

    def post(self, url, *, json=None, **_):
        self.post_calls.append((url, json or {}))
        if not self._post_responses:
            return _FakeResponse(200, json_data={})
        return self._post_responses.pop(0)

    def close(self):
        pass


def _innertube_action_response(
    continuation: str | None, messages: list[tuple[str, str]]
):
    actions = [
        {
            "addChatItemAction": {
                "item": {
                    "liveChatTextMessageRenderer": {
                        "id": f"m{i}",
                        "authorName": {"simpleText": author},
                        "authorExternalChannelId": f"UC{i}",
                        "timestampUsec": "1700000000000000",
                        "message": {"runs": [{"text": text}]},
                    }
                }
            }
        }
        for i, (author, text) in enumerate(messages)
    ]
    lcc: dict = {"actions": actions}
    if continuation:
        lcc["continuations"] = [
            {
                "invalidationContinuationData": {
                    "continuation": continuation,
                    "timeoutMs": 1000,
                }
            }
        ]
    else:
        lcc["continuations"] = []
    return _FakeResponse(
        200, json_data={"continuationContents": {"liveChatContinuation": lcc}}
    )


def test_poller_yields_messages_and_advances_continuation():
    client = _FakeClient(
        watch_html=_bootstrap_html(api_key="K1", continuation="C0"),
        post_responses=[
            _innertube_action_response("C1", [("alice", "hi")]),
            _innertube_action_response("C2", [("bob", "yo"), ("carol", "hey")]),
            _innertube_action_response(None, []),
        ],
    )
    sleeps: list[float] = []
    poller = _YouTubeLiveChatPoller(
        "https://www.youtube.com/watch?v=test", client=client, sleep=sleeps.append
    )
    entries = list(poller)
    assert [e["message"] for e in entries] == ["hi", "yo", "hey"]
    assert [e["author"]["name"] for e in entries] == ["alice", "bob", "carol"]
    # enumerate() restarts per innertube response, so UC ids repeat across them
    assert [e["author_id"] for e in entries] == ["UC0", "UC0", "UC1"]
    assert [body["continuation"] for _, body in client.post_calls] == ["C0", "C1", "C2"]
    for url, _ in client.post_calls:
        assert "key=K1" in url
        assert "prettyPrint=false" in url
    assert sleeps == [1.0, 1.0]


def test_poller_stops_when_no_continuation():
    client = _FakeClient(
        watch_html=_bootstrap_html(continuation="C0"),
        post_responses=[_innertube_action_response(None, [("a", "bye")])],
    )
    entries = list(_YouTubeLiveChatPoller("u", client=client, sleep=lambda _: None))
    assert len(entries) == 1
    assert len(client.post_calls) == 1


def test_poller_retries_on_429_then_succeeds():
    client = _FakeClient(
        watch_html=_bootstrap_html(continuation="C0"),
        post_responses=[
            _FakeResponse(429),
            _innertube_action_response(None, [("a", "ok")]),
        ],
    )
    sleeps: list[float] = []
    entries = list(_YouTubeLiveChatPoller("u", client=client, sleep=sleeps.append))
    assert len(entries) == 1
    assert len(client.post_calls) == 2
    assert sleeps[0] == 1.0


def test_poller_raises_after_max_429s():
    client = _FakeClient(
        watch_html=_bootstrap_html(continuation="C0"),
        post_responses=[_FakeResponse(429) for _ in range(10)],
    )
    with pytest.raises(httpx.HTTPStatusError):
        list(_YouTubeLiveChatPoller("u", client=client, sleep=lambda _: None))


def test_poller_raises_bootstrap_error_on_broken_page():
    client = _FakeClient(watch_html="<html>nothing useful here</html>")
    with pytest.raises(_YouTubeBootstrapError):
        list(_YouTubeLiveChatPoller("u", client=client, sleep=lambda _: None))


# --- provider ---


@pytest.mark.asyncio
async def test_youtube_provider_maps_entries():
    entries = [
        {
            "message_id": "1",
            "author": {"name": "alice"},
            "author_id": "UC1",
            "message": "Hey",
            "timestamp": None,
        },
        {
            "message_id": "3",
            "author": {"name": "carol"},
            "message": "Hi",
            "timestamp": None,
        },
    ]
    provider = YouTubeProvider("somechannel")
    with patch.object(
        provider,
        "_open_chat",
        return_value=("https://www.youtube.com/watch?v=AbCdEfGh123", iter(entries)),
    ):
        msgs = [m async for m in provider.messages()]

    assert len(msgs) == 2
    assert msgs[0].author == "alice"
    assert msgs[0].author_id == "UC1"
    assert msgs[0].stream_id == "AbCdEfGh123"
    assert msgs[1].stream_id == "AbCdEfGh123"


@pytest.mark.asyncio
async def test_youtube_provider_exits_when_chat_ends():
    provider = YouTubeProvider("somechannel")
    with patch.object(
        provider, "_open_chat", return_value=("https://x/watch?v=abc", iter([]))
    ):
        msgs = [m async for m in provider.messages()]
    assert msgs == []


@pytest.mark.asyncio
async def test_youtube_messages_yields_system_on_open_chat_failure():
    provider = YouTubeProvider("somechannel")
    with patch.object(
        provider,
        "_open_chat",
        side_effect=RuntimeError("Unable to parse initial video data"),
    ):
        msgs = [m async for m in provider.messages()]
    assert len(msgs) == 1
    assert msgs[0].platform == "system"
    assert "Unable to parse initial video data" in msgs[0].text


def test_youtube_live_url_builds_from_channel():
    assert (
        YouTubeProvider("somechannel").live_url
        == "https://www.youtube.com/@somechannel/live"
    )
    assert YouTubeProvider("@handle").live_url == "https://www.youtube.com/@handle/live"
