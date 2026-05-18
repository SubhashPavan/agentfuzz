from __future__ import annotations

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class NetworkPartition(Fault):
    """Simulate transport-layer failure on a tool call.

    Distinct from `ToolTimeout`: a timeout means a response came too slowly;
    a partition means no response came at all (DNS failed, TCP refused, TLS
    handshake error, connection reset mid-stream). Agents that catch
    `TimeoutError` but not `ConnectionError` slip through unit tests and
    crash in production.

    By default the fault raises a `ConnectionError` from the wrapped tool —
    this is the realistic shape. Set `as_result=True` to return an error
    envelope instead, for agents that handle networked tools as result
    objects rather than throwing-and-catching.

    Args:
        rate: Probability per call.
        as_result: If True, return an error-flagged ToolResult instead of
            raising. Default False (raise).
        only_tools: If set, only these tools are affected.
    """

    def __init__(
        self,
        *,
        rate: float = 0.05,
        as_result: bool = False,
        only_tools: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        self.rate = rate
        self.as_result = as_result
        self.only_tools = set(only_tools) if only_tools else None

    def on_tool_call(self, ctx: FaultContext, call: ToolCall) -> FaultDecision:
        if self.only_tools is not None and call.name not in self.only_tools:
            return FaultDecision.passthrough()
        if ctx.rng.random() >= self.rate:
            return FaultDecision.passthrough()

        if not self.as_result:
            ctx.record(
                "fault_blocked",
                fault=self.name,
                reason=f"connection refused on {call.name}",
            )
            ctx.tags.add("network_partition")
            raise ConnectionError(f"connection refused: {call.name}")

        synthetic = ToolResult(
            call_id=call.call_id,
            content={
                "error": "connection refused",
                "errno": 111,
                "code": "network_partition",
            },
            is_error=True,
            elapsed_ms=20.0,
        )
        return FaultDecision(
            outcome=FaultOutcome.BLOCKED,
            mutated_result=synthetic,
            reason=f"network partition on {call.name}",
        )
