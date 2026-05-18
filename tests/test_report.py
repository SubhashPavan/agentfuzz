from __future__ import annotations

from pathlib import Path

from agentfuzz import Harness, faults
from agentfuzz.adapters import CallableAdapter


def test_html_report_writes_file(tmp_path: Path) -> None:
    def agent(state: dict[str, object]) -> dict[str, object]:
        state["call_tool"]("ping")  # type: ignore[operator]
        return {**state, "answer": "ok", "token_usage": 10}

    wrapped = CallableAdapter(tools={"ping": lambda: "pong"}).wrap(agent)
    harness = Harness(wrapped, scenarios=[{"prompt": "p"}])
    harness.add(faults.ToolTimeout(rate=0.5))
    result = harness.run(iterations=8)

    out = tmp_path / "report.html"
    written = result.html(out)
    assert written.exists()
    body = written.read_text(encoding="utf-8")
    assert "agentfuzz report" in body
    assert "ToolTimeout" in body or "Pass rate" in body


def test_json_export_roundtrip(tmp_path: Path) -> None:
    def agent(state: dict[str, object]) -> dict[str, object]:
        return {**state, "answer": "ok", "token_usage": 5}

    wrapped = CallableAdapter().wrap(agent)
    harness = Harness(wrapped, scenarios=[{"prompt": "p"}])
    result = harness.run(iterations=3)

    out = tmp_path / "result.json"
    result.json(out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert '"total": 3' in text
