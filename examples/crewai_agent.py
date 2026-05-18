"""A CrewAI agent under fault injection.

CrewAI is built around real LLMs (it uses LiteLLM internally) and does not
ship a first-class deterministic fake model, so this example is structured
so the *interesting part* — wrap_tools and the fault chain — runs without
any API keys, while the full crew-loop path is exercised only when an
`OPENAI_API_KEY` (or similar provider key) is present.

What you'll see:

  1. Without keys: a direct call to a fuzzed CrewAI tool inside an
     `active_run` block, showing how a ToolTimeout fault flows through
     the adapter. Always runs.

  2. With keys: a full Crew that uses the same fuzzed tool. Drop in your
     own LLM config (Crew(... agent=Agent(llm=...))) and run.

Install:
    pip install "agentfuzz[crewai]"
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from agentfuzz import Harness, faults
from agentfuzz.adapters.crewai import CrewAIAdapter, wrap_tools
from agentfuzz.core.context import FaultContext
from agentfuzz.core.runtime import active_run


class LookupArgs(BaseModel):
    order_id: str = Field(description="Order ID to look up")


def _build_lookup_tool() -> Any:
    """Define a minimal CrewAI tool. Defined inside a function so importing
    this example doesn't require crewai unless the user runs it."""
    from crewai.tools import BaseTool as CrewaiBaseTool

    class LookupOrder(CrewaiBaseTool):
        name: str = "lookup_order"
        description: str = "Look up an order by id."
        args_schema: type[BaseModel] = LookupArgs

        def _run(self, order_id: str) -> dict:
            return {"order_id": order_id, "status": "shipped", "amount": 89.99}

    return LookupOrder()


def demo_wrap_tools_only() -> None:
    """The deterministic, key-free demo. Shows fault injection on a
    CrewAI tool without standing up a Crew."""
    tool = _build_lookup_tool()
    fuzzed = wrap_tools([tool])[0]

    # 1) Passthrough — outside a harness run, the wrapped tool just forwards.
    print("Passthrough:", fuzzed.run(order_id="44892"))

    # 2) Under a ToolTimeout fault — the tool returns a synthesized
    # timeout result instead of the real one.
    ctx = FaultContext(iteration=0, seed=2026)
    timeout = faults.ToolTimeout(rate=1.0)
    timeout.on_iteration_start(ctx)
    with active_run(ctx, [timeout]):
        result = fuzzed.run(order_id="44892")
    print("Under ToolTimeout:", result)
    print("Triggered events:", [e["type"] for e in ctx.events])


def demo_full_crew() -> None:
    """Full crew loop. Requires OPENAI_API_KEY (or another LiteLLM-supported
    provider). Skip silently if no key is configured."""
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        print("\n[skipping full crew demo — set OPENAI_API_KEY to run]")
        return

    from crewai import Agent, Crew, Process, Task

    tool = _build_lookup_tool()
    fuzzed = wrap_tools([tool])

    agent = Agent(
        role="Support representative",
        goal="Help users with their order questions.",
        backstory="You are a helpful customer-support agent.",
        tools=fuzzed,
        verbose=False,
    )
    task = Task(
        description="Look up the user's order {prompt} and report status.",
        expected_output="A one-sentence status update for the order.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

    wrapped = CrewAIAdapter(crew, prompt_key="prompt").wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "44892"}], seed=11)
    harness.add(faults.ToolTimeout(rate=0.25))
    harness.add(faults.MalformedToolResponse(rate=0.25))

    print("\nRunning agentfuzz against a CrewAI crew...")
    result = harness.run(iterations=4)
    print(result.summary())


if __name__ == "__main__":
    demo_wrap_tools_only()
    demo_full_crew()
