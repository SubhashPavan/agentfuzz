<div align="center">

# agentfuzz

**Chaos engineering for AI agents.**

Your agent works in the demo. In production it breaks because a tool times out,
an API returns garbage JSON, a user injects a prompt, or it spirals into an
infinite tool-call loop burning $200 in tokens. `agentfuzz` finds those failures
before your users do.

[![PyPI](https://img.shields.io/pypi/v/agentfuzz.svg)](https://pypi.org/project/agentfuzz/)
[![Python](https://img.shields.io/pypi/pyversions/agentfuzz.svg)](https://pypi.org/project/agentfuzz/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#status)

</div>

---

## Why this exists

Netflix built Chaos Monkey because cloud apps that passed unit tests still went
down in production — the failures were in *the seams between systems*, not the
systems themselves. AI agents have the same problem, with a worse blast radius:

- A flaky tool returns malformed JSON → your agent hallucinates plausible-looking
  arguments and writes them to your database.
- A user pastes a "translate this" prompt that's actually `IGNORE PREVIOUS
  INSTRUCTIONS` → your support agent emails the customer your system prompt.
- A model upgrade changes how the agent retries a 429 → the agent enters an
  infinite loop and burns through your monthly token budget in 40 minutes.

These failures don't show up in unit tests because unit tests assume the seams
work. `agentfuzz` deliberately breaks the seams.

## What it does

Wrap your agent. Pick a fault profile. Run. Get a report.

```python
from agentfuzz import Harness, faults

harness = Harness(my_agent)

harness.add(faults.ToolTimeout(rate=0.10))
harness.add(faults.MalformedToolResponse(rate=0.05))
harness.add(faults.PromptInjection.suite("owasp-llm01"))
harness.add(faults.CostSpiral(max_tokens=50_000))
harness.add(faults.LatencyJitter(p99_ms=8000))
harness.add(faults.PartialToolFailure())

report = harness.run(scenarios="tau-bench-airline", iterations=200)
report.html("./report.html")
```

You get:

- **Pass-rate per fault category** — "your agent survives malformed JSON 78% of
  the time but only 12% of timeout cases."
- **Cost-blast radius** — "fault X caused token usage to spike 14×."
- **Tool-call failure modes** — hallucinated arguments, retry storms, infinite
  loops.
- **Prompt-injection survival** — OWASP LLM01 suite results.
- **Replay traces** — the exact transcript that broke your agent, so you can
  fix it.

## Install

```bash
pip install agentfuzz                       # core
pip install "agentfuzz[langgraph]"          # + LangGraph adapter
pip install "agentfuzz[crewai]"             # + CrewAI adapter
pip install "agentfuzz[autogen]"            # + AutoGen adapter
pip install "agentfuzz[all]"                # everything
```

## 60-second example

```python
from agentfuzz import Harness, faults
from my_app import build_agent

harness = Harness(build_agent())
harness.add(faults.MalformedToolResponse(rate=0.2))
harness.add(faults.ToolTimeout(rate=0.1))

result = harness.run(iterations=50)
print(result.summary())
# >>> agentfuzz: 32/50 passed (64%)
# >>>   MalformedToolResponse: 8 failures
# >>>     - 5× hallucinated arguments
# >>>     - 3× silent corruption
# >>>   ToolTimeout: 10 failures
# >>>     - 7× retry storm (avg 14 retries)
# >>>     - 3× infinite loop killed at max_tokens
```

## Fault library

| Fault | What it simulates |
|---|---|
| `ToolTimeout` | A downstream API hangs past the agent's patience |
| `MalformedToolResponse` | Garbage JSON, truncated payloads, wrong schema |
| `PartialToolFailure` | Tool returns 200 then errors mid-stream |
| `LatencyJitter` | Realistic p50 / p99 latency distribution |
| `CostSpiral` | Detects runaway token usage above a threshold |
| `PromptInjection` | OWASP LLM01 catalog of injection payloads |
| `PromptParaphrase` | Real users mangle messages — typos, filler, contractions |
| `RateLimitBurst` | Cascading 429s from upstream APIs |
| `SchemaDrift` | Tool API changed shape between dev and prod |
| `AuthExpiry` | 401 / 403 — tests credential-refresh paths |
| `NetworkPartition` | Connection refused / TLS error — distinct from timeout |

More planned — [see the roadmap](docs/roadmap.md).

## Supported agent frameworks

- ✅ **LangGraph** (`agentfuzz[langgraph]`) — wrap your tools with `wrap_tools()`, point a `LangGraphAdapter` at your compiled graph, done. See [`examples/langgraph_react_agent.py`](examples/langgraph_react_agent.py).
- ✅ **Plain Python callables** — any `Callable[[State], State]`. Simplest way to try the tool.
- 🚧 CrewAI, AutoGen, PydanticAI, OpenAI Swarm, LlamaIndex — coming.

The adapter interface is small (`is_available()` + `wrap()`); PRs welcome.

## Status

**Alpha (v0.1).** API will change. Built and tested on Python 3.10–3.13.
The fault catalog is informed by production multi-agent deployments at
enterprise scale — but every codebase fails in its own special way, so file
issues when you find a fault we should ship.

## Why I'm building this

I've spent the last decade architecting AI systems for enterprises — including
multi-agent platforms running across 2,600+ production sites. The failures
that hurt are almost never the ones the unit tests check for. They're the
quiet, partial, half-degraded ones in the seams.

This is the tool I wish I'd had.

— [Pavan Subhash Tirumalasetti](https://www.linkedin.com/in/pavan-subhash-tirumalasetti)

## License

Apache 2.0. Use it commercially. Cite it in papers. Build a paid product on
top. Just don't claim you wrote it.

## Citing

If you use `agentfuzz` in research or production reports:

```bibtex
@software{agentfuzz,
  author  = {Tirumalasetti, Pavan Subhash},
  title   = {agentfuzz: Chaos engineering for AI agents},
  year    = {2026},
  url     = {https://github.com/SubhashPavan/agentfuzz},
}
```
