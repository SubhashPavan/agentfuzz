# Contributing to agentfuzz

Thanks for thinking about contributing — small, well-scoped PRs are very
welcome, especially:

- New fault types (see [`src/agentfuzz/faults/`](src/agentfuzz/faults/) for
  the pattern — a fault is a small class implementing one or two hooks).
- New framework adapters (CrewAI, AutoGen, PydanticAI, Swarm, LlamaIndex).
- Scenario suites — particularly anything modeled on real production
  workloads with permission to share.
- HTML report polish, CLI ergonomics, docs.

## Local setup

```bash
git clone https://github.com/SubhashPavan/agentfuzz.git
cd agentfuzz
python -m venv .venv
source .venv/bin/activate     # or .venv\Scripts\activate on Windows
pip install -e ".[langgraph,dev]"
```

Verify your setup:

```bash
pytest
ruff check src tests
ruff format --check src tests
agentfuzz demo
```

All three must pass before you open a PR.

## Adding a new fault

A fault subclasses `agentfuzz.Fault` and overrides the hooks it needs.
Default implementations of every hook are passthrough, so a fault that only
corrupts results overrides just `on_tool_result`. The shape:

```python
from agentfuzz import Fault, FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import FaultDecision, FaultOutcome


class MyFault(Fault):
    def __init__(self, *, rate: float = 0.1, name: str | None = None) -> None:
        super().__init__(name=name)
        self.rate = rate

    def on_tool_result(self, ctx: FaultContext, call: ToolCall, result: ToolResult) -> FaultDecision:
        if ctx.rng.random() >= self.rate:
            return FaultDecision.passthrough()
        # ... mutate result, return a FaultDecision(MUTATED, mutated_result=...)
```

**Determinism.** Always use `ctx.rng` (not `random.random()`). The harness
seeds it per iteration so runs are reproducible.

**Reporting.** If your fault detects a class of failure post-hoc (e.g. an
infinite loop), add a tag in `on_iteration_end`:

```python
ctx.tags.add("my_failure_tag")
ctx.tags.add("fault_triggered_failure")  # tells the harness to fail the iteration
```

**Tests.** Add tests covering both the trigger path and the non-trigger path.
Aim for the test patterns in [`tests/test_harness.py`](tests/test_harness.py).

## Adding a new framework adapter

Implement `agentfuzz.adapters.base.Adapter`:

- `is_available()` — return True iff the framework is importable.
- `wrap(...)` — return an `AgentCallable` that drives the framework.
  Inside the call, set `agentfuzz.core.runtime.active_run(ctx, faults)` and
  route the framework's tool calls through `compose_tool_call` /
  `compose_tool_result`.

The LangGraph adapter in
[`src/agentfuzz/adapters/langgraph.py`](src/agentfuzz/adapters/langgraph.py)
is the reference pattern.

## Style

- **Python 3.10+**, modern type hints.
- **ruff** for lint + format. CI runs both.
- **No new comments unless they explain a non-obvious _why_** — the codebase
  is intentionally low-comment.
- **No emojis in code or docs** unless they're part of an existing line.
- **No new external dependencies** without a strong reason; the core package
  has four (typer, rich, pydantic, jinja2). Framework deps go in extras.

## PR checklist

- [ ] `pytest` passes locally
- [ ] `ruff check src tests` passes
- [ ] `ruff format --check src tests` passes
- [ ] New behavior has a test
- [ ] PR description explains _why_, not just _what_

## License

By contributing, you agree your contribution is licensed under the project's
Apache 2.0 license.
