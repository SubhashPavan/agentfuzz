# Roadmap

Living document. Reorders based on community feedback and what shows up in
issues. Pull requests against any of the unchecked items are very welcome —
see [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the patterns.

## v0.2 — Framework reach (next release)

The goal of v0.2 is to make `agentfuzz` usable on the four agent frameworks
most teams ship today.

- [x] LangGraph adapter (sync + async tool wrapping via `wrap_tools`)
- [x] AuthExpiry, NetworkPartition, PromptParaphrase faults
- [ ] CrewAI adapter — `wrap_tools()` over `crewai.tools.BaseTool`,
      `CrewAIAdapter(crew)` for harness integration
- [ ] AutoGen v0.4+ adapter — wrap `FunctionTool` instances, support the
      async invocation pattern
- [ ] PydanticAI adapter — `Tool` wrapping + `Agent.run()` integration
- [ ] LangChain classic `AgentExecutor` adapter — for users still on the
      pre-LangGraph stack
- [ ] Switch the LangGraph tests off of the deprecated
      `langgraph.prebuilt.create_react_agent` to
      `langchain.agents.create_agent` once it's stable

## v0.3 — Fault catalog expansion

New faults that fit existing hooks; ranked by frequency in real
production-failure reports.

- [ ] `ContextWindowOverflow` — pad the conversation history with junk to
      push key instructions out of the model's window
- [ ] `ModelDowntime` — simulate the LLM API itself being unavailable (503
      from OpenAI / Anthropic / Bedrock / Azure)
- [ ] `ThoughtCorruption` — corrupt intermediate `AIMessage` content
      between tool calls (probes ReAct robustness)
- [ ] `ToolDescriptionPoisoning` — modify the tool description the LLM
      sees (adversarial schema injection)
- [ ] `MemoryDrift` — for stateful agents, corrupt cross-turn memory
- [ ] `EnvVarMissing` — strip an env var the tool depends on
- [ ] `HumanInTheLoopTimeout` — for HITL nodes, no human ever responds
- [ ] `DataDrift` — slowly mutate tool results across iterations
      (versioning issue simulation)

## v0.4 — Reporting and scenarios

- [ ] HTML report v2: interactive iteration timeline, per-iteration replay,
      tool-call graph
- [ ] JUnit XML output for CI integration
- [ ] OpenTelemetry trace export
- [ ] tau-bench (Sierra) scenario loader — run real benchmark tasks under
      fault injection
- [ ] WorkArena (ServiceNow) scenario loader
- [ ] Custom scenario format: load JSONL fixtures with prompt + expected
      grading rubric

## v0.5 — Production telemetry

- [ ] Mode for shadow-mode injection in production: real traffic, fault
      injected at low rate, comparison report against baseline
- [ ] `agentfuzz watch` — daemon that emits Prometheus metrics
- [ ] Replay traces from production into the harness for regression testing

## v1.0 — Stability

- [ ] API stability promise
- [ ] Docs site (mkdocs material) with API reference
- [ ] At least one major framework maintainer endorsement
- [ ] Used in CI by ≥5 publicly-listed projects

## Out of scope (for now)

- **Defending agents from prompt injection at runtime.** `agentfuzz` finds
  attacks; it doesn't prevent them. Runtime guardrails are a different tool
  (NeMo Guardrails, Lakera, Llama Guard).
- **Replacing the LLM itself for testing.** `agentfuzz` runs against your
  real agent (or a deterministic fake for CI). It doesn't generate
  synthetic responses from a smaller model.
- **General-purpose Python fuzzing.** Use Hypothesis or AFL for that.

## How to influence this

- 👍 react on issues that are most important to you — direct signal.
- File an issue describing a production failure mode that isn't yet on the
  list. The catalog is the moat; failures we've never seen are blind spots.
- Open a PR. Adding a fault is genuinely small — see the pattern in
  [`src/agentfuzz/faults/timeout.py`](../src/agentfuzz/faults/timeout.py).
