"""LangGraph adapter — stub. Real implementation lands in a follow-up.

The plan is to wrap each `ToolNode` (or each individual tool callable inside a
compiled StateGraph) with a shim that routes through `compose_tool_call` and
`compose_tool_result`. This requires either:

  1. Re-binding ToolNode's `tools_by_name` mapping after compilation, or
  2. Patching the model's tool-call dispatch via a langgraph "interrupt".

Both work; (1) is faster for v0.1 but only catches tools registered via
ToolNode. (2) handles custom dispatch but needs more glue.

This file is intentionally empty of logic so users importing the adapter get
a clear NotImplementedError until v0.2.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agentfuzz.adapters.base import Adapter, AgentCallable
from agentfuzz.core.fault import Fault


class LangGraphAdapter(Adapter):
    framework_name = "langgraph"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import langgraph  # noqa: F401
        except ImportError:
            return False
        return True

    def wrap(self, agent: Any, *, faults: Sequence[Fault]) -> AgentCallable:
        raise NotImplementedError(
            "LangGraphAdapter is a v0.2 target. Track progress: "
            "https://github.com/SubhashPavan/agentfuzz/issues/1"
        )
