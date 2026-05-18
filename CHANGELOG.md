# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-05-18

### Added

- **CrewAI adapter** (`agentfuzz[crewai]`) — `wrap_tools()` returns proxy
  `crewai.tools.BaseTool` instances that route invocations through the
  fault chain; `CrewAIAdapter(crew)` drives a `Crew` from the harness via
  `crew.kickoff()`. Supports sync and async tools. The full crew-loop
  integration test (deterministic fake LLM inside CrewAI's LiteLLM layer)
  is a v0.3.x follow-up.
- **LangChain 1.x coverage** — verified the existing `LangGraphAdapter`
  works on `langchain.agents.create_agent` output (it's a
  `CompiledStateGraph`, same type that `langgraph.prebuilt.create_react_agent`
  returns). No new adapter code; tests + example migrated off the
  deprecated import and the `LangGraphDeprecatedSinceV10` warning we'd
  been carrying is now silent.
- Example: `examples/crewai_agent.py` — runs the wrap_tools path without
  API keys, plus a full-crew demo that activates when `OPENAI_API_KEY` is
  set.

### Internal

- 5 new CrewAI tests; full suite now at 26 tests, all green.
- CI installs the `crewai` extra so CrewAI tests run on every push.

## [0.2.0] — 2026-05-18

### Added

- **`AuthExpiry`** fault — returns 401 / 403 from a fraction of tool
  calls. Surfaces agents that lack a credential-refresh path.
- **`NetworkPartition`** fault — simulates transport-layer failure
  (connection refused / TLS error). Distinct from `ToolTimeout`, which
  returns a delayed envelope. Raises `ConnectionError` by default; pass
  `as_result=True` for an error-envelope shape.
- **`PromptParaphrase`** fault — mutates user prompts the way real users
  do: typos, casual prefixes / suffixes, contractions. Template-driven, no
  LLM dependency.
- `docs/roadmap.md` — public roadmap covering v0.2 framework expansion,
  v0.3 fault catalog, v0.4 reporting / scenarios, v0.5 production
  telemetry, v1.0 stability.
- `docs/launch/seed-issues.md` — six pre-drafted GitHub issues covering
  framework adapters (CrewAI, AutoGen), the next fault types, JUnit XML
  output, deprecation cleanup, and a real-LLM examples gallery.

### Internal

- 7 new tests covering the new faults; full suite now at 21 tests, all
  green across Python 3.10 / 3.11 / 3.12 / 3.13.

## [0.1.0] — 2026-05-18

### Added

- **Harness** — drive an agent through fault-injected iterations with
  deterministic seeding, per-iteration `FaultContext`, scenario fixtures,
  and a `HarnessResult` with `summary()` / `json()` / `html()` exports.
- **Fault library (8):** `ToolTimeout`, `MalformedToolResponse` (six
  corruption modes), `PartialToolFailure`, `LatencyJitter`, `CostSpiral`
  (observer — tags infinite loops and token-budget blow-ups),
  `PromptInjection` (bundled OWASP LLM01 catalog with canary-phrase leak
  detection), `RateLimitBurst` (cascading 429 windows), and `SchemaDrift`
  (field renames and envelope wrapping).
- **LangGraph adapter** — `wrap_tools()` returns drop-in `StructuredTool`
  replacements that route through the fault chain; `LangGraphAdapter(graph)`
  drives a compiled graph from the harness using a contextvar-based runtime.
  Sync and async tools both supported.
- **Callable adapter** — for plain Python agent functions, no framework
  required.
- **HTML report** — styled output with stat cards, failures-by-fault,
  failures-by-tag, and a per-iteration table.
- **CLI** (`agentfuzz`) — `demo`, `faults`, `scenarios` subcommands.
- **Tests** — 14 covering harness lifecycle, determinism, every fault
  category, HTML/JSON rendering, and full LangGraph ReAct integration via a
  scripted fake chat model.
- **CI** — ruff lint + format check on 3.12; pytest on 3.10 / 3.11 / 3.12 /
  3.13 (Ubuntu) plus 3.12 smoke runs on Windows and macOS.

[Unreleased]: https://github.com/SubhashPavan/agentfuzz/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/SubhashPavan/agentfuzz/releases/tag/v0.3.0
[0.2.0]: https://github.com/SubhashPavan/agentfuzz/releases/tag/v0.2.0
[0.1.0]: https://github.com/SubhashPavan/agentfuzz/releases/tag/v0.1.0
