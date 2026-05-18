"""In-app AI rail backed by Anthropic Haiku 4.5 with tool-use.

The service streams an agentic loop:

  1. Send messages + tool definitions to Anthropic.
  2. Stream text deltas back to the caller as SSE events.
  3. If the model emits a ``tool_use`` block, run it via :mod:`finclaide.ai_tools`
     and append a ``tool_result`` to the messages, then resume the loop.
  4. Exit when the model returns ``end_turn`` or when ``MAX_TOOL_ITERATIONS``
     is reached (defensive bound — typical questions resolve in 0–2 hops).

The route handler is responsible for turning the generator into a Flask
``text/event-stream`` response. The generator yields already-serialised SSE
strings (``data: ...\\n\\n``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from finclaide.ai_tools import (
    DISPATCH,
    TOOL_DEFINITIONS,
    current_month_label,
    dispatch,
    today_label,
)

if TYPE_CHECKING:
    from finclaide.config import AppConfig
    from finclaide.services import ServiceContainer


logger = logging.getLogger(__name__)


MAX_TOOL_ITERATIONS = 6
DEFAULT_MAX_TOKENS = 1024


SYSTEM_PROMPT = """You are Finclaide, the in-app assistant for a single-household personal-finance app.

Hard rules:
- All monetary values in tool results are integer **milliunits** (divide by 1000 for dollars).
- Never invent numbers. If a tool call is needed, make it. If a question is outside your tools,
  say so plainly.
- Be terse. Two or three sentences is usually right. Use bullets only when listing 3+ items.
- When the user asks about "this month", default to {current_month}. Today is {today}.
- Plan vs actual, projections, and recommendations all live behind specific tools listed below.
  Prefer get_review for "how am I doing", get_summary for hard numbers, and get_rebalance_prompts
  when the user wants to fix an overage.
- This rail is **read-only** in v1. You cannot edit the plan, sync YNAB, or run reconciles.
  When the user asks for those, name the page they should go to (/plan, /operate) instead.
"""


@dataclass(frozen=True)
class _AnthropicCall:
    """The bits we need from a model response to keep the agentic loop going."""

    text_blocks: list[str]
    tool_uses: list[dict[str, Any]]
    stop_reason: str | None


class AIServiceUnavailable(RuntimeError):
    """Raised when the AI service is not configured (no API key)."""


def _sse(event: dict[str, Any]) -> str:
    return "data: " + json.dumps(event, default=str) + "\n\n"


class AIService:
    def __init__(
        self,
        *,
        config: "AppConfig",
        container: "ServiceContainer",
        anthropic_factory: Any | None = None,
    ):
        self._config = config
        self._container = container
        # The factory is overridable for tests so we never hit the real API
        # when ANTHROPIC_API_KEY is set by accident in CI.
        self._anthropic_factory = anthropic_factory

    @property
    def available(self) -> bool:
        return bool(self._config.anthropic_api_key)

    def chat(self, messages: list[dict[str, Any]], *, month: str | None = None) -> Iterator[str]:
        """Stream an SSE response for the given conversation. ``messages`` is in
        Anthropic's user/assistant format (already validated upstream)."""

        if not self.available and self._anthropic_factory is None:
            yield _sse({"type": "error", "code": "ai_unavailable", "message": "ANTHROPIC_API_KEY is not set."})
            return

        client = self._build_client()
        if client is None:
            yield _sse({"type": "error", "code": "ai_unavailable", "message": "Anthropic SDK unavailable."})
            return

        system = SYSTEM_PROMPT.format(
            current_month=month or current_month_label(),
            today=today_label(),
        )

        # ``messages`` accumulates across the agentic loop so each subsequent
        # call sees prior assistant text + tool_use + tool_result blocks.
        loop_messages = list(messages)

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                call = yield from self._stream_one_turn(client=client, messages=loop_messages, system=system)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("AI streaming failed")
                yield _sse({"type": "error", "code": "ai_failed", "message": str(exc)})
                return

            assistant_blocks: list[dict[str, Any]] = []
            if call.text_blocks:
                assistant_blocks.append({"type": "text", "text": "".join(call.text_blocks)})
            for tu in call.tool_uses:
                assistant_blocks.append({"type": "tool_use", "id": tu["id"], "name": tu["name"], "input": tu["input"]})

            if assistant_blocks:
                loop_messages.append({"role": "assistant", "content": assistant_blocks})

            if not call.tool_uses or call.stop_reason != "tool_use":
                yield _sse({"type": "done", "stop_reason": call.stop_reason or "end_turn"})
                return

            tool_result_blocks: list[dict[str, Any]] = []
            for tu in call.tool_uses:
                yield _sse(
                    {
                        "type": "tool_use",
                        "id": tu["id"],
                        "name": tu["name"],
                        "input": tu["input"],
                    }
                )
                result_block = self._run_tool(tu)
                tool_result_blocks.append(result_block)
                yield _sse(
                    {
                        "type": "tool_result",
                        "id": tu["id"],
                        "name": tu["name"],
                        "is_error": result_block.get("is_error", False),
                        "result": _maybe_parse(result_block.get("content")),
                    }
                )
            loop_messages.append({"role": "user", "content": tool_result_blocks})

        yield _sse({"type": "done", "stop_reason": "max_iterations"})

    def _stream_one_turn(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        system: str,
    ) -> Iterator[str]:
        text_chunks: list[str] = []
        tool_uses_by_index: dict[int, dict[str, Any]] = {}
        tool_input_strs: dict[int, str] = {}
        stop_reason: str | None = None

        with client.messages.stream(
            model=self._config.anthropic_model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        ) as stream:
            for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if getattr(block, "type", None) == "tool_use":
                        tool_uses_by_index[event.index] = {
                            "id": block.id,
                            "name": block.name,
                            "input": {},
                        }
                        tool_input_strs[event.index] = ""
                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        text_chunks.append(delta.text)
                        yield _sse({"type": "text_delta", "delta": delta.text})
                    elif dtype == "input_json_delta":
                        tool_input_strs[event.index] = tool_input_strs.get(event.index, "") + (
                            delta.partial_json or ""
                        )
                elif etype == "content_block_stop":
                    if event.index in tool_uses_by_index:
                        raw = tool_input_strs.get(event.index, "")
                        try:
                            tool_uses_by_index[event.index]["input"] = json.loads(raw) if raw else {}
                        except json.JSONDecodeError:
                            tool_uses_by_index[event.index]["input"] = {}
                elif etype == "message_delta":
                    delta = getattr(event, "delta", None)
                    if delta is not None:
                        stop_reason = getattr(delta, "stop_reason", None) or stop_reason
                elif etype == "message_stop":
                    pass

            final_message = stream.get_final_message()
            stop_reason = stop_reason or getattr(final_message, "stop_reason", None)

        return _AnthropicCall(
            text_blocks=text_chunks,
            tool_uses=list(tool_uses_by_index.values()),
            stop_reason=stop_reason,
        )

    def _run_tool(self, tu: dict[str, Any]) -> dict[str, Any]:
        name = tu["name"]
        args = tu.get("input") or {}
        if name not in DISPATCH:
            return {
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "is_error": True,
                "content": json.dumps({"error": f"unknown tool: {name}"}),
            }
        try:
            result = dispatch(self._container, name, args)
        except Exception as exc:  # noqa: BLE001 — surface tool errors to the model
            logger.warning("Tool %s failed: %s", name, exc)
            return {
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "is_error": True,
                "content": json.dumps({"error": str(exc), "tool": name}),
            }
        return {
            "type": "tool_result",
            "tool_use_id": tu["id"],
            "content": json.dumps(result, default=str),
        }

    def _build_client(self) -> Any | None:
        if self._anthropic_factory is not None:
            return self._anthropic_factory(self._config.anthropic_api_key or "")
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - requirement listed in pyproject
            logger.error("anthropic SDK not installed")
            return None
        return anthropic.Anthropic(api_key=self._config.anthropic_api_key or "")


def _maybe_parse(blob: Any) -> Any:
    """Return JSON-parsed content when ``blob`` is a JSON string, else as-is."""
    if not isinstance(blob, str):
        return blob
    try:
        return json.loads(blob)
    except (TypeError, json.JSONDecodeError):
        return blob
