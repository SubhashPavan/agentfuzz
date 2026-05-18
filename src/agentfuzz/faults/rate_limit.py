from __future__ import annotations

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class RateLimitBurst(Fault):
    """Simulate a window of cascading 429s from upstream APIs.

    Rate limits don't trigger one-at-a-time — when one fires, several usually
    follow. This fault flips on a "burst" period at random intervals; while
    active, every tool call gets a 429. Once the cooldown elapses, calls flow
    again. Exposes agents with naïve "retry immediately" loops.

    Args:
        burst_probability: Per-call probability of entering a burst window.
        burst_length: Number of subsequent tool calls that also fail with 429.
        only_tools: If set, only these tools participate in the burst.
    """

    def __init__(
        self,
        *,
        burst_probability: float = 0.05,
        burst_length: int = 4,
        only_tools: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= burst_probability <= 1.0:
            raise ValueError(f"burst_probability must be in [0,1], got {burst_probability}")
        if burst_length <= 0:
            raise ValueError("burst_length must be positive")
        self.burst_probability = burst_probability
        self.burst_length = burst_length
        self.only_tools = set(only_tools) if only_tools else None
        # Per-iteration state lives in ctx.events rather than self to keep the
        # fault stateless across iterations.

    def _remaining(self, ctx: FaultContext) -> int:
        for ev in reversed(ctx.events):
            if ev.get("type") == "ratelimit_burst_state" and ev.get("fault") == self.name:
                return int(ev.get("remaining", 0))
        return 0

    def _set_remaining(self, ctx: FaultContext, remaining: int) -> None:
        ctx.events.append(
            {"type": "ratelimit_burst_state", "fault": self.name, "remaining": remaining}
        )

    def on_tool_call(self, ctx: FaultContext, call: ToolCall) -> FaultDecision:
        if self.only_tools is not None and call.name not in self.only_tools:
            return FaultDecision.passthrough()

        remaining = self._remaining(ctx)
        in_burst = remaining > 0
        if not in_burst and ctx.rng.random() < self.burst_probability:
            in_burst = True
            remaining = self.burst_length

        if not in_burst:
            return FaultDecision.passthrough()

        self._set_remaining(ctx, remaining - 1)
        synthetic = ToolResult(
            call_id=call.call_id,
            content={"error": "rate_limited", "status": 429, "retry_after_ms": 1_500},
            is_error=True,
            elapsed_ms=50.0,
        )
        return FaultDecision(
            outcome=FaultOutcome.BLOCKED,
            mutated_result=synthetic,
            reason=f"429 burst (remaining {remaining - 1})",
        )
