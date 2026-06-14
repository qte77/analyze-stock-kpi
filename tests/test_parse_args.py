"""Tests for :mod:`analyze_stock_kpi.utils.parse_args` — CLI args parsing."""

from __future__ import annotations

from pathlib import Path

from analyze_stock_kpi.utils.parse_args import CliArgs


def test_refresh_universe_flag_default_none() -> None:
    """Without ``--refresh-universe``, the field is ``None``."""
    args = CliArgs.model_construct()
    assert args.refresh_universe is None


def test_refresh_universe_flag_accepts_orchestrator_name() -> None:
    """``--refresh-universe federal-contractors`` populates the field."""
    args = CliArgs.model_construct(refresh_universe="federal-contractors")
    assert args.refresh_universe == "federal-contractors"


def test_output_and_audit_output_default_none() -> None:
    """``--output`` and ``--audit-output`` default to ``None``."""
    args = CliArgs.model_construct()
    assert args.output is None
    assert args.audit_output is None


def test_output_and_audit_output_accept_path_overrides() -> None:
    """Explicit paths populate the override fields."""
    args = CliArgs.model_construct(
        output=Path("/tmp/preset.txt"),  # noqa: S108  # nosec B108
        audit_output=Path("/tmp/audit.json"),  # noqa: S108  # nosec B108
    )
    assert args.output == Path("/tmp/preset.txt")  # noqa: S108  # nosec B108
    assert args.audit_output == Path("/tmp/audit.json")  # noqa: S108  # nosec B108
