from __future__ import annotations

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultDecision, FaultOutcome


class AuthExpiry(Fault):
    """Simulate expired credentials at the tool boundary.

    Tool calls return 401 or 403 at random. Surfaces agents that lack a
    credential-refresh path: they either retry the same call indefinitely
    (cost spiral), bubble the error to the user verbatim ("Unauthorized"
    is unhelpful), or worst, treat the 401 body as a valid result and
    proceed with garbage.

    Args:
        rate: Probability of injecting an auth error on any tool call.
        status: 401 (expired) or 403 (insufficient permissions). Some
            agent logic branches differently on these — test both.
        only_tools: If set, only these tools experience auth errors.
    """

    def __init__(
        self,
        *,
        rate: float = 0.1,
        status: int = 401,
        only_tools: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        if status not in {401, 403}:
            raise ValueError(f"status must be 401 or 403, got {status}")
        self.rate = rate
        self.status = status
        self.only_tools = set(only_tools) if only_tools else None

    def on_tool_call(self, ctx: FaultContext, call: ToolCall) -> FaultDecision:
        if self.only_tools is not None and call.name not in self.only_tools:
            return FaultDecision.passthrough()
        if ctx.rng.random() >= self.rate:
            return FaultDecision.passthrough()

        message = "credential expired" if self.status == 401 else "insufficient permissions"
        synthetic = ToolResult(
            call_id=call.call_id,
            content={"error": message, "status": self.status, "code": "auth_expired"},
            is_error=True,
            elapsed_ms=80.0,
        )
        return FaultDecision(
            outcome=FaultOutcome.BLOCKED,
            mutated_result=synthetic,
            reason=f"injected {self.status} on {call.name}",
        )
