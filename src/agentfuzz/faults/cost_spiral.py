from __future__ import annotations

from agentfuzz.core.context import FaultContext, ToolCall
from agentfuzz.core.fault import Fault, FaultDecision


class CostSpiral(Fault):
    """Detect agents that enter runaway token-consumption loops.

    Not an injector — an observer. Tags the iteration as a failure when token
    usage exceeds `max_tokens` or when the same tool is called more than
    `max_repeated_calls` times consecutively (a classic retry-storm signature).

    Args:
        max_tokens: Token budget per iteration. Exceeding it tags the run.
        max_repeated_calls: If the same tool is invoked this many times in a
            row, the iteration is tagged as an infinite-loop suspect.
    """

    def __init__(
        self,
        *,
        max_tokens: int = 50_000,
        max_repeated_calls: int = 8,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if max_repeated_calls <= 0:
            raise ValueError("max_repeated_calls must be positive")
        self.max_tokens = max_tokens
        self.max_repeated_calls = max_repeated_calls

    def on_tool_call(self, ctx: FaultContext, call: ToolCall) -> FaultDecision:
        ctx.tool_calls.append(call)
        # Check tail for repeated calls to the same tool.
        if len(ctx.tool_calls) >= self.max_repeated_calls:
            tail = ctx.tool_calls[-self.max_repeated_calls :]
            if all(c.name == call.name for c in tail):
                ctx.tags.add("infinite_loop_suspect")
                ctx.tags.add("fault_triggered_failure")
                ctx.record(
                    "cost_spiral_detected",
                    fault=self.name,
                    kind="repeated_tool",
                    tool=call.name,
                    streak=self.max_repeated_calls,
                )
        return FaultDecision.passthrough()

    def on_iteration_end(self, ctx: FaultContext) -> None:
        if ctx.token_usage > self.max_tokens:
            ctx.tags.add("cost_spiral")
            ctx.tags.add("fault_triggered_failure")
            ctx.record(
                "cost_spiral_detected",
                fault=self.name,
                kind="token_budget_exceeded",
                used=ctx.token_usage,
                budget=self.max_tokens,
            )
