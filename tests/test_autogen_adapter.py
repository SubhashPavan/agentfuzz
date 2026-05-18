"""AutoGen v0.4+ adapter tests.

These exercise `wrap_tools` directly (without standing up an
AssistantAgent + model client through the real LLM). The full agent-loop
path is structurally complete but its integration test (deterministic
fake model client) is a v0.3.x follow-up tracked in docs/roadmap.md.
"""

from __future__ import annotations

import pytest

pytest.importorskip("autogen_core")

from autogen_core import CancellationToken
from autogen_core.tools import FunctionTool

from agentfuzz import faults
from agentfuzz.adapters.autogen import wrap_tools
from agentfuzz.core.context import FaultContext
from agentfuzz.core.runtime import active_run


async def _async_lookup(order_id: str) -> str:
    """Look up an order asynchronously."""
    return f"order {order_id}: shipped"


def _sync_lookup(order_id: str) -> str:
    """Look up an order synchronously."""
    return f"order {order_id}: shipped"


def _async_tool() -> FunctionTool:
    return FunctionTool(_async_lookup, description="Async order lookup")


def _sync_tool() -> FunctionTool:
    return FunctionTool(_sync_lookup, description="Sync order lookup")


def test_wrap_tools_preserves_identity() -> None:
    fuzzed = wrap_tools([_async_tool()])[0]
    assert fuzzed.name == "_async_lookup"
    assert fuzzed.description == "Async order lookup"
    # Schema must include `order_id` — proxy must expose original signature
    assert "order_id" in fuzzed.schema["parameters"]["properties"]


def test_wrap_tools_rejects_non_function_tool() -> None:
    with pytest.raises(TypeError, match=r"FunctionTool"):
        wrap_tools(["not a tool"])


@pytest.mark.asyncio
async def test_passthrough_outside_active_run() -> None:
    fuzzed = wrap_tools([_async_tool()])[0]
    result = await fuzzed.run_json({"order_id": "X"}, CancellationToken())
    assert result == "order X: shipped"


@pytest.mark.asyncio
async def test_timeout_fault_blocks_async_tool() -> None:
    fuzzed = wrap_tools([_async_tool()])[0]
    ctx = FaultContext(iteration=0, seed=1)
    fault = faults.ToolTimeout(rate=1.0)
    fault.on_iteration_start(ctx)
    with active_run(ctx, [fault]):
        result = await fuzzed.run_json({"order_id": "X"}, CancellationToken())
    assert isinstance(result, dict)
    assert result.get("error") == "timeout"
    blocked = [ev for ev in ctx.events if ev.get("type") == "fault_blocked"]
    assert len(blocked) == 1
    assert blocked[0]["fault"] == "ToolTimeout"


@pytest.mark.asyncio
async def test_timeout_fault_blocks_sync_tool() -> None:
    fuzzed = wrap_tools([_sync_tool()])[0]
    ctx = FaultContext(iteration=0, seed=1)
    fault = faults.ToolTimeout(rate=1.0)
    fault.on_iteration_start(ctx)
    with active_run(ctx, [fault]):
        result = await fuzzed.run_json({"order_id": "X"}, CancellationToken())
    assert isinstance(result, dict)
    assert result.get("error") == "timeout"


@pytest.mark.asyncio
async def test_malformed_response_corrupts_tool_result() -> None:
    fuzzed = wrap_tools([_async_tool()])[0]
    ctx = FaultContext(iteration=0, seed=42)
    fault = faults.MalformedToolResponse(rate=1.0)
    fault.on_iteration_start(ctx)
    with active_run(ctx, [fault]):
        await fuzzed.run_json({"order_id": "X"}, CancellationToken())
    triggered = any(
        ev.get("type") == "fault_mutated" and ev.get("fault") == "MalformedToolResponse"
        for ev in ctx.events
    )
    assert triggered
