"""A LangGraph ReAct agent under fault injection.

This example uses a *deterministic fake model* so you can run it without any
API key. The fake model is scripted to: (1) emit a tool call, then (2) emit a
final answer. The interesting part isn't the model — it's that the
fault-injected `lookup_order` tool sometimes returns timeouts, malformed
responses, or corrupted shapes, and we observe how the ReAct loop reacts.

To run against a real model (OpenAI / Anthropic / Azure / Bedrock), swap the
`_FakeChat` instantiation for any tool-calling chat model.

Run:
    python examples/langgraph_react_agent.py
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agentfuzz import Harness, faults
from agentfuzz.adapters.langgraph import LangGraphAdapter, wrap_tools


@tool
def lookup_order(order_id: str) -> dict:
    """Look up an order by id and return its status and amount."""
    return {"order_id": order_id, "status": "shipped", "amount": 89.99}


class _FakeChat(GenericFakeChatModel):
    """A tool-calling fake LLM. The scripted messages drive a fixed ReAct
    trajectory: emit one tool call, then emit a final answer."""

    def bind_tools(self, tools, **kwargs):  # type: ignore[override, no-untyped-def]
        return self


def _scripted_round() -> list[AIMessage]:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "lookup_order", "args": {"order_id": "44892"}, "id": "call_1"}
            ],
        ),
        AIMessage(content="Order 44892 is shipped."),
    ]


def main() -> None:
    # Build a fresh model for each iteration; the scripted message iterator
    # would otherwise be drained.
    def build_graph() -> object:
        model = _FakeChat(messages=iter(_scripted_round()))
        return create_react_agent(model, tools=wrap_tools([lookup_order]))

    # The harness will re-invoke `agent` for each iteration. We close over
    # `build_graph` to make a fresh graph + fresh scripted-message iterator
    # per call.
    def agent_callable(state: dict) -> dict:
        return LangGraphAdapter(build_graph()).wrap()(state)

    harness = Harness(
        agent_callable,
        scenarios=[{"prompt": "Where is order 44892?"}],
        seed=2026,
    )
    harness.add(faults.ToolTimeout(rate=0.2))
    harness.add(faults.MalformedToolResponse(rate=0.2))
    harness.add(faults.SchemaDrift(rate=0.15))
    harness.add(faults.LatencyJitter(p50_ms=50, p99_ms=1_500))

    print("Running agentfuzz against a LangGraph ReAct agent…")
    result = harness.run(iterations=20)
    print(result.summary())

    out = Path("agentfuzz_reports/langgraph.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    result.html(out)
    print(f"\nHTML report: {out}")


if __name__ == "__main__":
    main()
