from __future__ import annotations

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class PartialToolFailure(Fault):
    """Simulate a tool that returns 200 but then errors mid-stream.

    Common in long-running tools (file uploads, batch jobs, streaming
    responses). The agent sees a success envelope wrapping an error payload —
    a classic place where retry logic forgets to actually inspect the body.
    """

    def __init__(
        self,
        *,
        rate: float = 0.05,
        only_tools: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        self.rate = rate
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

        synthetic = ToolResult(
            call_id=result.call_id,
            content={
                "status": "ok",
                "partial": True,
                "error": "downstream worker crashed after partial completion",
                "completed_at_step": ctx.rng.randrange(1, 8),
                "original_content": result.content,
            },
            is_error=False,
            elapsed_ms=result.elapsed_ms,
        )
        return FaultDecision(
            outcome=FaultOutcome.MUTATED,
            mutated_result=synthetic,
            reason=f"partial failure on {call.name}",
        )
