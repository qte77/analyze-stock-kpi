"""Project version — single source of truth is pyproject.toml's [project].version."""

from importlib.metadata import version

__version__: str = version("analyze-stock-kpi")
__authors__: str = "qte77"
