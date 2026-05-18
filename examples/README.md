# agentfuzz examples

Each example is a small, runnable script that shows one shape of agent
under fault injection. Run them after `pip install -e ..` from the repo
root.

| File | What it shows |
|---|---|
| [`toy_support_agent.py`](toy_support_agent.py) | A bare callable agent with one tool, run under timeout + malformed-response + injection faults. The "hello world" of agentfuzz. |
| `langgraph_agent.py` | Coming in v0.2: a LangGraph ReAct agent under the same fault profile. |

To run the toy example:

```bash
python examples/toy_support_agent.py
```

You'll see a summary printed to stdout and an HTML report written to
`./agentfuzz_reports/toy.html`.
