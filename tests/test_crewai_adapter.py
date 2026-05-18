"""CrewAI adapter tests.

These exercise `wrap_tools` directly (without running a full CrewAI Crew
through a real LLM). The full crew-loop path is structurally complete but
its integration test (deterministic fake LLM inside CrewAI's LiteLLM layer)
is a v0.3.x follow-up tracked in docs/roadmap.md.
"""

from __future__ import annotations

import pytest

pytest.importorskip("crewai")

from pydantic import BaseModel, Field

from agentfuzz import faults
from agentfuzz.adapters.crewai import wrap_tools
from agentfuzz.core.context import FaultContext
from agentfuzz.core.runtime import active_run


def _make_lookup_tool() -> object:
    from crewai.tools import BaseTool as CrewaiBaseTool

    class LookupArgs(BaseModel):
        order_id: str = Field(description="Order ID")

    class LookupOrder(CrewaiBaseTool):
        name: str = "lookup_order"
        description: str = "Look up an order by id."
        args_schema: type[BaseModel] = LookupArgs

        def _run(self, order_id: str) -> dict:
            return {"order_id": order_id, "status": "shipped", "amount": 50.0}

    return LookupOrder()


def test_wrap_tools_preserves_identity() -> None:
    original = _make_lookup_tool()
    fuzzed = wrap_tools([original])[0]
    assert fuzzed.name == "lookup_order"
    # CrewAI re-mangles description with auto-prefixed metadata; the original
    # text must still be embedded somewhere in the rendered version.
    assert "Look up an order by id." in fuzzed.description
    assert fuzzed.args_schema is original.args_schema


def test_wrap_tools_passthrough_outside_run() -> None:
    fuzzed = wrap_tools([_make_lookup_tool()])[0]
    out = fuzzed.run(order_id="X")
    assert out == {"order_id": "X", "status": "shipped", "amount": 50.0}


def test_timeout_fault_blocks_crewai_tool_invocation() -> None:
    fuzzed = wrap_tools([_make_lookup_tool()])[0]
    ctx = FaultContext(iteration=0, seed=7)
    fault = faults.ToolTimeout(rate=1.0)
    fault.on_iteration_start(ctx)
    with active_run(ctx, [fault]):
        result = fuzzed.run(order_id="X")
    assert isinstance(result, dict)
    assert result.get("error") == "timeout"
    blocked = [ev for ev in ctx.events if ev.get("type") == "fault_blocked"]
    assert len(blocked) == 1
    assert blocked[0]["fault"] == "ToolTimeout"


def test_malformed_response_corrupts_crewai_tool_result() -> None:
    fuzzed = wrap_tools([_make_lookup_tool()])[0]
    ctx = FaultContext(iteration=0, seed=42)
    fault = faults.MalformedToolResponse(rate=1.0)
    fault.on_iteration_start(ctx)
    with active_run(ctx, [fault]):
        fuzzed.run(order_id="X")
    triggered = any(
        ev.get("type") == "fault_mutated" and ev.get("fault") == "MalformedToolResponse"
        for ev in ctx.events
    )
    assert triggered


def test_rejects_non_crewai_tool() -> None:
    with pytest.raises(TypeError, match=r"crewai\.tools\.BaseTool"):
        wrap_tools(["not a tool"])
