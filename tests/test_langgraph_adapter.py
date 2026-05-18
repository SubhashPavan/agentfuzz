"""LangGraph adapter tests.

These tests exercise the adapter against a real LangGraph runtime using a
deterministic fake chat model — no network, no API keys.

The agent is built via `langchain.agents.create_agent` (LangChain 1.x), which
returns a `CompiledStateGraph` — the same type `langgraph.prebuilt.create_react_agent`
returns on the older API. The `LangGraphAdapter` works for both call sites
because it only touches the compiled-graph contract."""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langchain_core")
pytest.importorskip("langchain")

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agentfuzz import Harness, faults
from agentfuzz.adapters.langgraph import LangGraphAdapter, wrap_tools
from agentfuzz.core.context import FaultContext
from agentfuzz.core.runtime import active_run


@tool
def lookup_order(order_id: str) -> dict:
    """Look up an order by id."""
    return {"order_id": order_id, "status": "shipped", "amount": 50.0}


def test_wrap_tools_preserves_identity() -> None:
    fuzzed = wrap_tools([lookup_order])[0]
    assert fuzzed.name == "lookup_order"
    assert fuzzed.description.strip() == "Look up an order by id."
    assert fuzzed.args_schema is lookup_order.args_schema


def test_wrap_tools_passthrough_outside_run() -> None:
    """When invoked outside a harness run, fuzzed tools must just forward."""
    fuzzed = wrap_tools([lookup_order])[0]
    out = fuzzed.invoke({"order_id": "abc"})
    assert out == {"order_id": "abc", "status": "shipped", "amount": 50.0}


def test_timeout_fault_blocks_langgraph_tool_calls() -> None:
    fuzzed = wrap_tools([lookup_order])[0]
    ctx = FaultContext(iteration=0, seed=1)
    timeout = faults.ToolTimeout(rate=1.0)
    timeout.on_iteration_start(ctx)
    with active_run(ctx, [timeout]):
        result = fuzzed.invoke({"order_id": "abc"})
    assert isinstance(result, dict)
    assert result.get("error") == "timeout"


def test_malformed_response_corrupts_langgraph_tool_results() -> None:
    fuzzed = wrap_tools([lookup_order])[0]
    ctx = FaultContext(iteration=0, seed=42)
    malformed = faults.MalformedToolResponse(rate=1.0)
    malformed.on_iteration_start(ctx)
    with active_run(ctx, [malformed]):
        fuzzed.invoke({"order_id": "abc"})
    # Some corruption mode applied — either the dict is mutated or the result
    # is a string / wrapped envelope, depending on the random mode.
    triggered = any(
        ev.get("type") == "fault_mutated" and ev.get("fault") == "MalformedToolResponse"
        for ev in ctx.events
    )
    assert triggered


class _ToolCallingFakeModel(GenericFakeChatModel):
    """GenericFakeChatModel doesn't implement bind_tools, which create_react_agent
    requires. We override to no-op (the scripted messages already encode the
    tool calls we want to emit)."""

    def bind_tools(self, tools, **kwargs):  # type: ignore[override, no-untyped-def]
        return self


def _scripted_messages() -> list[AIMessage]:
    return [
        AIMessage(
            content="",
            tool_calls=[{"name": "lookup_order", "args": {"order_id": "44892"}, "id": "call_1"}],
        ),
        AIMessage(content="Order 44892 is shipped."),
    ]


def _fake_react_agent() -> object:
    """Build a real LangGraph ReAct agent driven by a scripted fake LLM.

    Round 1: the LLM emits a tool call to lookup_order.
    Round 2: after the tool result, the LLM emits a final answer.
    """
    model = _ToolCallingFakeModel(messages=iter(_scripted_messages()))
    fuzzed = wrap_tools([lookup_order])
    return create_agent(model, tools=fuzzed)


def test_full_harness_run_against_langgraph_react_agent() -> None:
    graph = _fake_react_agent()
    wrapped = LangGraphAdapter(graph).wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "Where is order 44892?"}])
    result = harness.run(iterations=1)
    assert result.total == 1
    # The fake model emits exactly one tool call per iteration.
    iter_result = result.iterations[0]
    assert "shipped" in (iter_result.events[-1].get("text") or "").lower()


def test_timeout_fault_propagates_through_react_loop() -> None:
    # Re-build the agent inside the test so the GenericFakeChatModel script
    # isn't drained from a previous test.
    graph = _fake_react_agent()
    wrapped = LangGraphAdapter(graph).wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "Where is order 44892?"}])
    harness.add(faults.ToolTimeout(rate=1.0))
    result = harness.run(iterations=1)
    triggered = result.iterations[0].triggered_faults
    assert "ToolTimeout" in triggered
