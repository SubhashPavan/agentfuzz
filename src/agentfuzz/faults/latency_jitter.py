from __future__ import annotations

import time

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class LatencyJitter(Fault):
    """Inject realistic latency distributions into tool calls.

    Production tools rarely have flat latency. The dangerous failures appear
    in the tail: a p99 spike during a high-traffic window collides with a
    naïve retry policy and the agent dies of timeouts even though no single
    request actually failed.

    This fault doesn't block calls — it adds wall-clock latency to the result.
    Pair it with `ToolTimeout` to model a flaky upstream.

    Args:
        p50_ms: Median injected delay.
        p99_ms: Tail injected delay. Distribution is lognormal-ish: most calls
            near p50, occasional spikes near p99.
        actually_sleep: If True, blocks the thread (realistic). If False, just
            records the inflated elapsed_ms (fast for CI).
    """

    def __init__(
        self,
        *,
        p50_ms: float = 300.0,
        p99_ms: float = 5_000.0,
        actually_sleep: bool = False,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if p50_ms < 0 or p99_ms < p50_ms:
            raise ValueError("require 0 <= p50_ms <= p99_ms")
        self.p50_ms = p50_ms
        self.p99_ms = p99_ms
        self.actually_sleep = actually_sleep

    def on_tool_result(
        self, ctx: FaultContext, call: ToolCall, result: ToolResult
    ) -> FaultDecision:
        # 99th percentile lands on p99; rest follows a triangular distribution
        # weighted toward p50.
        u = ctx.rng.random()
        extra = self.p99_ms if u > 0.99 else ctx.rng.triangular(0.0, self.p99_ms, self.p50_ms)
        if self.actually_sleep:
            time.sleep(extra / 1000.0)
        new = ToolResult(
            call_id=result.call_id,
            content=result.content,
            is_error=result.is_error,
            elapsed_ms=result.elapsed_ms + extra,
        )
        ctx.record("latency_injected", tool=call.name, extra_ms=extra)
        return FaultDecision(
            outcome=FaultOutcome.MUTATED,
            mutated_result=new,
            reason=f"+{int(extra)}ms latency",
        )
