"""An AutoGen v0.4+ tool under fault injection.

Like the CrewAI example, the *interesting part* — wrap_tools and the fault
chain — runs without any API keys. The full AssistantAgent loop is gated
behind `OPENAI_API_KEY` because AutoGen's tool-calling flow needs a real
model client.

Install:
    pip install "agentfuzz[autogen]"
"""

from __future__ import annotations

import asyncio
import os

from autogen_core import CancellationToken
from autogen_core.tools import FunctionTool

from agentfuzz import Harness, faults
from agentfuzz.adapters.autogen import AutoGenAdapter, wrap_tools
from agentfuzz.core.context import FaultContext
from agentfuzz.core.runtime import active_run


async def lookup_order(order_id: str) -> str:
    """Look up an order and return its status."""
    return f"order {order_id}: shipped, amount $89.99"


async def demo_wrap_tools_only() -> None:
    """No API key needed — exercises wrap_tools and the fault chain directly."""
    tool = FunctionTool(lookup_order, description="Look up an order")
    fuzzed = wrap_tools([tool])[0]

    # 1) Passthrough — outside an active run.
    out = await fuzzed.run_json({"order_id": "44892"}, CancellationToken())
    print("Passthrough:", out)

    # 2) Under a ToolTimeout fault.
    ctx = FaultContext(iteration=0, seed=2026)
    timeout = faults.ToolTimeout(rate=1.0)
    timeout.on_iteration_start(ctx)
    with active_run(ctx, [timeout]):
        out = await fuzzed.run_json({"order_id": "44892"}, CancellationToken())
    print("Under ToolTimeout:", out)
    print("Triggered events:", [e["type"] for e in ctx.events])


def demo_full_agent() -> None:
    """Run a real AssistantAgent against the fuzzed tool. Needs OPENAI_API_KEY."""
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[skipping full AssistantAgent demo — set OPENAI_API_KEY to run]")
        return

    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    fuzzed = wrap_tools([FunctionTool(lookup_order, description="Look up an order")])
    model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")
    agent = AssistantAgent(
        name="support",
        model_client=model_client,
        tools=fuzzed,
        system_message="You help users with order status. Use the tool, then answer.",
    )

    wrapped = AutoGenAdapter(agent).wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "Where is order 44892?"}], seed=42)
    harness.add(faults.ToolTimeout(rate=0.3))
    harness.add(faults.MalformedToolResponse(rate=0.2))

    print("\nRunning agentfuzz against an AutoGen AssistantAgent...")
    result = harness.run(iterations=4)
    print(result.summary())


async def main() -> None:
    await demo_wrap_tools_only()
    demo_full_agent()


if __name__ == "__main__":
    asyncio.run(main())
