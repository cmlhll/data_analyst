import importlib


def test_reporter_module_can_import():
    mod = importlib.import_module("agents.reporter")
    assert hasattr(mod, "ReporterAgent")
