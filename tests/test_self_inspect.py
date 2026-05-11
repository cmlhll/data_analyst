import json
from pathlib import Path

import pytest

import self_inspect


def test_record_issue_writes_state_and_history(monkeypatch, tmp_path):
    monkeypatch.setattr(self_inspect.config, "SELF_INSPECT_DIR", str(tmp_path))
    state = {}

    issue = self_inspect.record_issue(
        state,
        category="CODE_FAILURE",
        severity="HIGH",
        detail="unit-test",
        agent_name="eda",
        duration_ms=123.0,
    )

    assert state["inspection_log"][0]["category"] == "CODE_FAILURE"
    assert issue["agent"] == "eda"

    history = tmp_path / "history.jsonl"
    assert history.exists()
    lines = history.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["detail"] == "unit-test"


def test_record_issue_rejects_unknown_values():
    with pytest.raises(ValueError):
        self_inspect.record_issue({}, "UNKNOWN", "HIGH", "x")

    with pytest.raises(ValueError):
        self_inspect.record_issue({}, "CODE_FAILURE", "SEV0", "x")


def test_postmortem_analyze_and_save(monkeypatch, tmp_path):
    monkeypatch.setattr(self_inspect.config, "SELF_INSPECT_DIR", str(tmp_path))
    analyzer = self_inspect.PostMortemAnalyzer(session_id="tdd")

    result = analyzer.analyze_and_save([
        {"category": "EXECUTION_SLOW", "severity": "MEDIUM", "agent": "eda", "detail": "slow", "duration_ms": 40000},
        {"category": "CODE_FAILURE", "severity": "HIGH", "agent": "ml", "detail": "trace"},
    ])

    assert result["summary"]["total"] == 2
    assert "优化建议" in result["report"]
    assert result["report_path"]
    assert Path(result["report_path"]).exists()
