"""Smoke test: verifies pytest + coverage + pythonpath wiring is functional."""

from src import __version__


def test_version_is_string() -> None:
    assert isinstance(__version__.__version__, str)
    assert __version__.__version__.count(".") == 2
