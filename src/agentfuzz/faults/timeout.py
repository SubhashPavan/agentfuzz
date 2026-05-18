from __future__ import annotations

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class ToolTimeout(Fault):
    """Simulate a tool that hangs past the agent's patience.

    Replaces a fraction of tool calls with a synthesized timeout result. This
    surfaces agents that retry forever, hallucinate alternative arguments, or
    fail to escalate gracefully.

    Args:
        rate: Probability in [0, 1] that any given tool call is replaced with
            a timeout. Independent per call.
        only_tools: If set, only these tool names may time out. Otherwise all.
        timeout_after_ms: The latency value attached to the synthesized result,
            for downstream cost / latency reporting.
    """

    def __init__(
        self,
        *,
        rate: float = 0.1,
        only_tools: list[str] | None = None,
        timeout_after_ms: float = 30_000.0,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        self.rate = rate
        self.only_tools = set(only_tools) if only_tools else None
        self.timeout_after_ms = timeout_after_ms

    def on_tool_call(self, ctx: FaultContext, call: ToolCall) -> FaultDecision:
        if self.only_tools is not None and call.name not in self.only_tools:
            return FaultDecision.passthrough()
        if ctx.rng.random() >= self.rate:
            return FaultDecision.passthrough()
        synthetic = ToolResult(
            call_id=call.call_id,
            content={"error": "timeout", "tool": call.name, "after_ms": self.timeout_after_ms},
            is_error=True,
            elapsed_ms=self.timeout_after_ms,
        )
        return FaultDecision(
            outcome=FaultOutcome.BLOCKED,
            mutated_result=synthetic,
            reason=f"injected timeout on {call.name}",
        )
