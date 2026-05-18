# Seed issues — paste these via the GitHub web UI before launch

A repo with zero open issues on launch day reads as "dead" or "no real
roadmap." Three to six well-written open issues read as "active project,
maintainer is approachable." These are written so a passing visitor can
self-select into a contribution — exactly the conversion you want during a
HN front-page surge.

**How to use:** open https://github.com/SubhashPavan/agentfuzz/issues/new
for each one. Paste the title and body, apply the suggested labels, then
**Submit new issue**. Total time: ~10 minutes.

You may need to create the labels first (one-time, takes 2 minutes):
Settings → Labels → New label. Suggested: `good first issue` (green),
`help wanted` (purple), `enhancement` (blue), `framework: crewai` /
`framework: autogen` / `framework: pydantic-ai` (each yellow), `fault`
(orange), `docs` (grey).

---

## Issue 1 — CrewAI adapter

**Title:** CrewAI adapter (mirror the LangGraph pattern)

**Labels:** `enhancement`, `help wanted`, `framework: crewai`

**Body:**

The LangGraph adapter (`src/agentfuzz/adapters/langgraph.py`) shows the
pattern: wrap each tool so its invocation flows through `compose_tool_call`
/ `compose_tool_result`, and use the contextvar-based runtime
(`agentfuzz.core.runtime.active_run`) to share the active `FaultContext`
between the harness and the tool wrappers.

CrewAI tools (`crewai.tools.BaseTool`) follow a similar shape to LangChain
tools — they expose a `_run` method we can override. The crew-level
integration would be:

```python
from agentfuzz.adapters.crewai import wrap_tools, CrewAIAdapter

fuzzed = wrap_tools(my_crew_tools)
crew = Crew(agents=[...], tools=fuzzed, ...)

wrapped = CrewAIAdapter(crew).wrap()
harness = Harness(wrapped, ...)
```

### Acceptance criteria
- [ ] `wrap_tools` over `crewai.tools.BaseTool`
- [ ] `CrewAIAdapter(crew).wrap()` returns an `AgentCallable`
- [ ] At least one integration test using a deterministic fake LLM
- [ ] `crewai` listed in `[project.optional-dependencies]` under
      `agentfuzz[crewai]`
- [ ] Example in `examples/crewai_*.py`

Happy to mentor anyone who wants to pick this up. The LangGraph adapter
test in `tests/test_langgraph_adapter.py` is the model.

---

## Issue 2 — AutoGen v0.4+ adapter

**Title:** AutoGen v0.4+ adapter

**Labels:** `enhancement`, `help wanted`, `framework: autogen`

**Body:**

AutoGen's v0.4 rewrite changed the tool model substantially — tools are
now `autogen_core.tools.FunctionTool` (or `BaseTool`) instances. The
adapter should:

- Wrap `FunctionTool` so invocations route through agentfuzz's fault chain
- Support both sync and async tools (AutoGen leans async)
- Expose `AutoGenAdapter(agent_or_team).wrap()` for the harness

See `src/agentfuzz/adapters/langgraph.py` and
`src/agentfuzz/core/runtime.py` for the pattern. Async support exists —
just route through `_arun` on the proxy.

### Acceptance criteria
- [ ] `wrap_tools` over `autogen_core.tools.FunctionTool`
- [ ] `AutoGenAdapter(...).wrap()`
- [ ] Integration test with deterministic fake model
- [ ] `agentfuzz[autogen]` extra wired up
- [ ] Example agent in `examples/`

---

## Issue 3 — `ModelDowntime` fault

**Title:** Add `ModelDowntime` fault — simulate LLM API unavailability

**Labels:** `enhancement`, `fault`, `good first issue`

**Body:**

The current fault catalog only injects at the *tool* layer. Real production
outages frequently come from the *model* layer — OpenAI returns 503,
Bedrock has a regional outage, Anthropic rate-limits your tier.

This fault doesn't need to mock the LLM directly. It can intercept the
LangGraph node that calls the model (or, for other adapters, the
equivalent), and return a synthetic error result. Tags the iteration as
`model_downtime` so the report breaks it out.

Open questions worth discussing in the issue:
1. Should this be a generic fault (raise from the model node) or
   framework-specific (LangGraphAdapter-only for v1)?
2. Probability per call vs. probability per *iteration* (a real outage
   affects every call in a window, not random calls).

### Acceptance criteria
- [ ] `ModelDowntime` fault class in `src/agentfuzz/faults/`
- [ ] At least one test covering the trigger and non-trigger paths
- [ ] README + roadmap.md updated

Good first issue — the fault hook model is small and the existing
`RateLimitBurst` fault is the closest pattern to follow.

---

## Issue 4 — JUnit XML report output

**Title:** Add JUnit XML output for CI integration

**Labels:** `enhancement`, `good first issue`

**Body:**

For agentfuzz to be useful as a CI gate ("fail the build if pass-rate
drops below 80%"), it needs to emit results in a format CI systems can
ingest. JUnit XML is the lingua franca.

Add a method `HarnessResult.junit_xml(path)` that writes a JUnit-compatible
XML file. One `<testcase>` per iteration; pass/fail/skipped based on the
iteration's `passed` flag and tags. Use the standard JUnit XSD —
[here's the schema](https://github.com/testmoapp/junitxml).

### Acceptance criteria
- [ ] `HarnessResult.junit_xml(path)` writes valid JUnit XML
- [ ] Test that round-trips through `xml.etree.ElementTree`
- [ ] Documented in the README
- [ ] CI example showing `agentfuzz` results in GitHub Actions test summary

Good first issue — self-contained, follows the existing `.json()` /
`.html()` pattern in `src/agentfuzz/core/result.py`.

---

## Issue 5 — Switch LangGraph tests off the deprecated `create_react_agent`

**Title:** Replace `langgraph.prebuilt.create_react_agent` with `langchain.agents.create_agent`

**Labels:** `enhancement`, `good first issue`

**Body:**

Our LangGraph adapter tests
(`tests/test_langgraph_adapter.py`) currently use
`langgraph.prebuilt.create_react_agent`, which emits a
`LangGraphDeprecatedSinceV10` warning. The replacement is
`from langchain.agents import create_agent`, which moved out of langgraph
into the main `langchain` package in v1.0.

The challenge: we don't want to pull `langchain` itself into our test
deps if `langchain-core` is enough. Investigation needed on whether
`create_agent` is reachable from just `langchain-core`, or if we need a
heavier dep.

Three acceptable resolutions:
1. Move tests onto `create_agent` and add `langchain` to the dev deps
2. Hand-roll the equivalent ReAct loop in the test fixture and avoid the
   prebuilt entirely
3. Silence the deprecation warning until LangGraph 2.0 lands

### Acceptance criteria
- [ ] LangGraph adapter tests pass without emitting deprecation warnings
- [ ] Decision documented in the PR description

---

## Issue 6 — Examples: real LLM runners for popular providers

**Title:** Examples gallery — agentfuzz against real OpenAI / Anthropic / Bedrock agents

**Labels:** `docs`, `good first issue`, `help wanted`

**Body:**

The existing example (`examples/langgraph_react_agent.py`) uses a
deterministic fake model so it runs without API keys. Useful for testing,
but doesn't let users see what fault injection *actually does* against a
real LLM.

Looking for community PRs adding real-model examples:
- `examples/openai_react_agent.py` — uses OpenAI's GPT-4o or 4o-mini
- `examples/anthropic_react_agent.py` — Claude Sonnet 4.5 or 4.6
- `examples/bedrock_react_agent.py` — any Bedrock-hosted model
- `examples/local_ollama_agent.py` — local model via Ollama for the
  "no API key" crowd

Each example should:
- Note in a comment at the top that an API key env var is required
- Demonstrate at least three faults with non-trivial rate
- Print the summary at the end so users can see the impact

### Acceptance criteria
- [ ] At least one new example, fully working
- [ ] README "Examples" section listing them
- [ ] None of the new examples are run in CI (we don't want to spend
      tokens in CI)

Multiple PRs welcome — one per provider is fine, no need to land them
together.
