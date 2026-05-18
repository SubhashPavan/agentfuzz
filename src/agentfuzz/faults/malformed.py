from __future__ import annotations

import json
from typing import Any

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome

_CORRUPTORS = (
    "truncate",
    "wrong_type",
    "extra_field",
    "missing_required",
    "invalid_json",
    "wrong_schema",
)


class MalformedToolResponse(Fault):
    """Corrupt successful tool responses in realistic ways.

    Real APIs misbehave in patterned ways: truncated payloads (proxies cut
    them off), wrong-typed fields (a number where a string is expected),
    extra/missing fields, invalid JSON strings, and shape drift. This fault
    rolls one of those corruptions for a fraction of successful results.

    Args:
        rate: Probability of corrupting any given successful result.
        modes: Which corruption modes are allowed. Default: all.
        only_tools: If set, only these tools may have their results corrupted.
    """

    def __init__(
        self,
        *,
        rate: float = 0.1,
        modes: list[str] | None = None,
        only_tools: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        if modes is not None:
            bad = set(modes) - set(_CORRUPTORS)
            if bad:
                raise ValueError(f"unknown corruption modes: {sorted(bad)}")
        self.rate = rate
        self.modes = tuple(modes) if modes else _CORRUPTORS
        self.only_tools = set(only_tools) if only_tools else None

    def on_tool_result(
        self, ctx: FaultContext, call: ToolCall, result: ToolResult
    ) -> FaultDecision:
        if result.is_error:
            return FaultDecision.passthrough()
        if self.only_tools is not None and call.name not in self.only_tools:
            return FaultDecision.passthrough()
        if ctx.rng.random() >= self.rate:
            return FaultDecision.passthrough()

        mode = ctx.rng.choice(self.modes)
        corrupted = _corrupt(result.content, mode, ctx)
        synthetic = ToolResult(
            call_id=result.call_id,
            content=corrupted,
            is_error=False,
            elapsed_ms=result.elapsed_ms,
        )
        return FaultDecision(
            outcome=FaultOutcome.MUTATED,
            mutated_result=synthetic,
            reason=f"corrupted result via {mode}",
        )


def _corrupt(content: Any, mode: str, ctx: FaultContext) -> Any:
    if mode == "invalid_json":
        # Return text that LOOKS like JSON but isn't parseable.
        return '{"status": "ok", "value": '  # deliberately unterminated
    if mode == "truncate":
        s = content if isinstance(content, str) else json.dumps(content, default=str)
        cut = max(1, int(len(s) * ctx.rng.uniform(0.2, 0.7)))
        return s[:cut]
    if mode == "wrong_type":
        if isinstance(content, dict):
            d = dict(content)
            for k in list(d.keys()):
                if isinstance(d[k], (int, float)):
                    d[k] = str(d[k])
                elif isinstance(d[k], str):
                    d[k] = 0
                break
            return d
        return str(content)
    if mode == "extra_field":
        if isinstance(content, dict):
            return {**content, "_debug_internal": "leaked_value_" + str(ctx.rng.randrange(1000))}
        return content
    if mode == "missing_required":
        if isinstance(content, dict) and content:
            d = dict(content)
            key = ctx.rng.choice(list(d.keys()))
            d.pop(key, None)
            return d
        return content
    if mode == "wrong_schema":
        return [content] if not isinstance(content, list) else {"items": content}
    return content
