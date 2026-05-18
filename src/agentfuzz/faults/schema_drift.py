from __future__ import annotations

from typing import Any

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class SchemaDrift(Fault):
    """Simulate a tool whose response shape changed between dev and prod.

    The classic 3am page: the vendor renamed `user_id` to `userId`, made
    `amount` a string instead of a number, or moved fields under a new
    envelope. Agents that key directly off field names break silently.

    Args:
        rate: Probability of mutating any given successful result.
        renames: Mapping of old field name → new field name to apply.
        wrap_in: If set, the entire response is wrapped under this key (e.g.
            `{"data": <original>}`).
        only_tools: If set, only these tools experience drift.
    """

    def __init__(
        self,
        *,
        rate: float = 0.1,
        renames: dict[str, str] | None = None,
        wrap_in: str | None = None,
        only_tools: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        if renames is None and wrap_in is None:
            # Default: snake_case → camelCase on top-level keys.
            renames = {}
        self.rate = rate
        self.renames = renames
        self.wrap_in = wrap_in
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

        content: Any = result.content
        if isinstance(content, dict):
            if self.renames is not None:
                renames = self.renames or _auto_snake_to_camel(content)
                content = {renames.get(k, k): v for k, v in content.items()}
            if self.wrap_in is not None:
                content = {self.wrap_in: content}
        elif self.wrap_in is not None:
            content = {self.wrap_in: content}

        new = ToolResult(
            call_id=result.call_id,
            content=content,
            is_error=False,
            elapsed_ms=result.elapsed_ms,
        )
        return FaultDecision(
            outcome=FaultOutcome.MUTATED,
            mutated_result=new,
            reason="schema drift applied",
        )


def _auto_snake_to_camel(d: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in d:
        if "_" in k:
            parts = k.split("_")
            out[k] = parts[0] + "".join(p.title() for p in parts[1:])
    return out
