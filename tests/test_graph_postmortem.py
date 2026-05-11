import graph


class _DummyApp:
    def stream(self, initial_state, run_cfg):
        # 模拟 reporter 节点输出一次
        yield {
            "reporter": {
                "report": "# 主报告",
            }
        }

    def get_state(self, run_cfg):
        class _S:
            values = {
                "report": "# 主报告",
                "inspection_log": [
                    {
                        "category": "CODE_FAILURE",
                        "severity": "HIGH",
                        "detail": "boom",
                        "agent": "eda",
                    }
                ],
            }

        return _S()


class _DummyAnalyzer:
    def __init__(self, session_id):
        self.session_id = session_id

    def analyze_and_save(self, inspection_log):
        assert inspection_log
        return {
            "report": "# 自检报告\n建议...",
            "report_path": "/tmp/self_inspect.md",
            "summary": {"total": len(inspection_log)},
        }


def test_run_analysis_appends_inspection_report(monkeypatch):
    monkeypatch.setattr(graph, "build_graph", lambda: _DummyApp())
    monkeypatch.setattr(graph, "PostMortemAnalyzer", _DummyAnalyzer)

    out = graph.run_analysis(file_path="data/iris.csv", user_query="q", thread_id="tid")

    assert "# 主报告" in out["report"]
    assert "# 自检报告" in out["report"]
    assert out["inspection_report"].startswith("# 自检报告")
