"""Core primitives — the small, stable surface that faults and adapters build on."""

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultOutcome
from agentfuzz.core.harness import Harness
from agentfuzz.core.result import HarnessResult, IterationResult
from agentfuzz.core.runtime import active_run, current_ctx, current_faults

__all__ = [
    "Fault",
    "FaultContext",
    "FaultOutcome",
    "Harness",
    "HarnessResult",
    "IterationResult",
    "ToolCall",
    "ToolResult",
    "active_run",
    "current_ctx",
    "current_faults",
]
