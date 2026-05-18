"""agentfuzz CLI — `agentfuzz` after install.

For v0.1 the CLI is intentionally small: list faults, list scenario suites,
and run the bundled smoke example. Users instrument their real agents via
the Python API. v0.2 will add `agentfuzz run path/to/config.toml`.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from agentfuzz import faults as fault_module
from agentfuzz import scenarios as scenario_module

app = typer.Typer(
    help="Chaos engineering for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command("faults")
def list_faults() -> None:
    """List built-in fault types."""
    table = Table(title="Available faults", show_lines=False)
    table.add_column("Name", style="bold")
    table.add_column("Summary")
    for name in fault_module.__all__:
        cls = getattr(fault_module, name)
        doc = (cls.__doc__ or "").strip().split("\n")[0]
        table.add_row(name, doc)
    console.print(table)


@app.command("scenarios")
def list_scenarios() -> None:
    """List built-in scenario suites."""
    table = Table(title="Scenario suites", show_lines=False)
    table.add_column("Name", style="bold")
    table.add_column("Count")
    for name in scenario_module.available_suites():
        table.add_row(name, str(len(scenario_module.load_scenarios(name))))
    console.print(table)


@app.command("demo")
def demo(
    iterations: Annotated[int, typer.Option(help="Number of iterations to run.")] = 20,
    report: Annotated[str | None, typer.Option(help="Path to write HTML report.")] = None,
) -> None:
    """Run a built-in demo: a toy agent against a smoke scenario suite
    under timeout + malformed-response faults. Useful for sanity-checking
    the install before instrumenting your own agent."""
    from agentfuzz import Harness, faults
    from agentfuzz.adapters import CallableAdapter

    def search(query: str) -> dict[str, object]:
        return {"results": [f"hit:{query}"], "n": 1}

    def toy_agent(state: dict[str, object]) -> dict[str, object]:
        """A 'realistic' agent: parses tool output by key. Breaks when shape is wrong."""
        call_tool = state["call_tool"]  # type: ignore[index]
        result = call_tool("search", query=state.get("prompt", ""))  # type: ignore[operator]
        # An agent built against a contract — fails when the contract is violated.
        if not isinstance(result, dict):
            return {
                **state,
                "error": f"expected dict, got {type(result).__name__}",
                "token_usage": 240,
            }
        if "n" not in result or "results" not in result:
            return {**state, "error": "missing required fields", "token_usage": 240}
        return {**state, "answer": f"found {result['n']} hits", "token_usage": 240}

    wrapped = CallableAdapter(tools={"search": search}).wrap(toy_agent)
    harness = Harness(wrapped, scenarios="smoke")
    harness.add(faults.ToolTimeout(rate=0.2))
    harness.add(faults.MalformedToolResponse(rate=0.3))
    harness.add(faults.LatencyJitter(p50_ms=50, p99_ms=400))

    console.print(f"[bold]Running {iterations} iterations…[/bold]")
    result = harness.run(iterations=iterations)
    console.print(result.summary())
    if report:
        path = result.html(report)
        console.print(f"\nHTML report written to [bold]{path}[/bold]")


if __name__ == "__main__":
    app()
