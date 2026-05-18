"""Tests for the AI rail scaffold.

The Anthropic client is always faked. We assert:
- Routes refuse when the API key is missing (503 ai_unavailable).
- Routes refuse bad payloads.
- The agentic loop dispatches a tool call and feeds its result back.
- Unknown tools surface as ``tool_result`` with ``is_error: true``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from finclaide.ai import AIService


class _FakeStreamEvent:
    def __init__(self, **kw: Any):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeStream:
    def __init__(self, events: list[Any], final_message: Any):
        self._events = events
        self._final = final_message

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self):
        return self._final


class _FakeMessages:
    def __init__(self, turns: list[list[Any]], stop_reasons: list[str]):
        self._turns = turns
        self._stop_reasons = stop_reasons
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> _FakeStream:
        # Deep-copy messages so later mutations of the caller's list don't
        # leak into our recording and obscure point-in-time assertions.
        snapshot = {**kwargs, "messages": [dict(m) for m in kwargs.get("messages", [])]}
        self.calls.append(snapshot)
        events = self._turns.pop(0)
        stop = self._stop_reasons.pop(0)
        return _FakeStream(events, final_message=_FakeStreamEvent(stop_reason=stop))


class _FakeAnthropic:
    def __init__(self, turns: list[list[Any]], stop_reasons: list[str]):
        self.messages = _FakeMessages(turns, stop_reasons)


def _text_delta(text: str) -> _FakeStreamEvent:
    return _FakeStreamEvent(
        type="content_block_delta",
        index=0,
        delta=_FakeStreamEvent(type="text_delta", text=text),
    )


def _tool_use_block(index: int, tool_id: str, name: str, partial_json: str) -> list[_FakeStreamEvent]:
    return [
        _FakeStreamEvent(
            type="content_block_start",
            index=index,
            content_block=_FakeStreamEvent(type="tool_use", id=tool_id, name=name),
        ),
        _FakeStreamEvent(
            type="content_block_delta",
            index=index,
            delta=_FakeStreamEvent(type="input_json_delta", partial_json=partial_json),
        ),
        _FakeStreamEvent(type="content_block_stop", index=index),
    ]


def _parse_sse(stream):
    out = []
    for chunk in stream:
        for line in chunk.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[len("data: "):]))
    return out


@pytest.fixture
def configured_app(app_factory, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    app = app_factory()
    return app


def test_chat_returns_503_without_api_key(app_factory):
    app = app_factory()
    client = app.test_client()
    response = client.post(
        "/ui-api/ai/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers={"X-Finclaide-UI": "1"},
    )
    assert response.status_code == 503
    assert response.get_json()["error"] == "ai_unavailable"


def test_chat_rejects_missing_messages(configured_app):
    client = configured_app.test_client()
    response = client.post(
        "/ui-api/ai/chat",
        json={"messages": []},
        headers={"X-Finclaide-UI": "1"},
    )
    assert response.status_code == 400


def test_chat_rejects_invalid_role(configured_app):
    client = configured_app.test_client()
    response = client.post(
        "/ui-api/ai/chat",
        json={"messages": [{"role": "system", "content": "no"}]},
        headers={"X-Finclaide-UI": "1"},
    )
    assert response.status_code == 400


def test_chat_streams_text_only_turn(configured_app):
    fake = _FakeAnthropic(
        turns=[[_text_delta("Hello "), _text_delta("world.")]],
        stop_reasons=["end_turn"],
    )
    container = configured_app.extensions["finclaide"]
    service = AIService(
        config=configured_app.config["FINCLAIDE_CONFIG"],
        container=container,
        anthropic_factory=lambda _key: fake,
    )
    events = _parse_sse(service.chat([{"role": "user", "content": "hi"}]))
    assert [e["delta"] for e in events if e["type"] == "text_delta"] == ["Hello ", "world."]
    assert events[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert fake.messages.calls[0]["tools"]  # tools list was forwarded


def test_chat_dispatches_known_tool_and_loops(configured_app):
    """The model asks for get_status, we dispatch, and the loop sends the result back."""
    tool_block = _tool_use_block(
        index=0,
        tool_id="toolu_1",
        name="get_status",
        partial_json="{}",
    )
    fake = _FakeAnthropic(
        turns=[
            tool_block,
            [_text_delta("Status looks fresh.")],
        ],
        stop_reasons=["tool_use", "end_turn"],
    )
    container = configured_app.extensions["finclaide"]
    service = AIService(
        config=configured_app.config["FINCLAIDE_CONFIG"],
        container=container,
        anthropic_factory=lambda _key: fake,
    )
    events = _parse_sse(service.chat([{"role": "user", "content": "status?"}]))
    tool_use_events = [e for e in events if e["type"] == "tool_use"]
    tool_result_events = [e for e in events if e["type"] == "tool_result"]
    assert tool_use_events[0]["name"] == "get_status"
    assert tool_result_events[0]["is_error"] is False
    # Final assistant turn streams text after the tool result.
    assert any(e["type"] == "text_delta" and "fresh" in e["delta"] for e in events)
    # The second stream call should have seen the tool_use + tool_result in messages.
    second_call_messages = fake.messages.calls[1]["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"


def test_chat_surfaces_unknown_tool_as_error(configured_app):
    tool_block = _tool_use_block(
        index=0,
        tool_id="toolu_x",
        name="not_a_real_tool",
        partial_json="{}",
    )
    fake = _FakeAnthropic(
        turns=[tool_block, [_text_delta("done")]],
        stop_reasons=["tool_use", "end_turn"],
    )
    container = configured_app.extensions["finclaide"]
    service = AIService(
        config=configured_app.config["FINCLAIDE_CONFIG"],
        container=container,
        anthropic_factory=lambda _key: fake,
    )
    events = _parse_sse(service.chat([{"role": "user", "content": "do the impossible"}]))
    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert tool_results and tool_results[0]["is_error"] is True
    assert tool_results[0]["result"]["error"].startswith("unknown tool")


def test_chat_terminates_at_max_iterations(configured_app):
    tool_block = _tool_use_block(
        index=0,
        tool_id="toolu_loop",
        name="get_status",
        partial_json="{}",
    )
    # Always emit a tool_use so the loop never naturally exits.
    fake = _FakeAnthropic(
        turns=[tool_block for _ in range(8)],
        stop_reasons=["tool_use" for _ in range(8)],
    )
    container = configured_app.extensions["finclaide"]
    service = AIService(
        config=configured_app.config["FINCLAIDE_CONFIG"],
        container=container,
        anthropic_factory=lambda _key: fake,
    )
    events = _parse_sse(service.chat([{"role": "user", "content": "loop"}]))
    assert events[-1] == {"type": "done", "stop_reason": "max_iterations"}
