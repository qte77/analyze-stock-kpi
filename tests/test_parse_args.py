"""Tests for :mod:`analyze_stock_kpi.utils.parse_args` — CLI args parsing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

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


def test_sortino_from_and_to_default_none() -> None:
    """Without the flags, both custom-window fields are ``None``."""
    args = CliArgs.model_construct()
    assert args.sortino_from is None
    assert args.sortino_to is None


def test_sortino_from_parsed_from_cli() -> None:
    """``--sortino-from`` parses an ISO date; ``--sortino-to`` stays unset."""
    args = CliArgs(_cli_parse_args=["--sortino-from", "2015-01-01"])  # type: ignore[call-arg]
    assert args.sortino_from == date(2015, 1, 1)
    assert args.sortino_to is None


def test_sortino_from_and_to_both_parsed_from_cli() -> None:
    """Both flags together parse into their respective fields."""
    args = CliArgs(  # type: ignore[call-arg]
        _cli_parse_args=["--sortino-from", "2015-01-01", "--sortino-to", "2020-12-31"]
    )
    assert args.sortino_from == date(2015, 1, 1)
    assert args.sortino_to == date(2020, 12, 31)


def test_sortino_from_after_to_rejected() -> None:
    """``--sortino-from`` >= ``--sortino-to`` fails fast with a clear message."""
    with pytest.raises(ValidationError, match="sortino-from"):
        CliArgs(  # type: ignore[call-arg]
            _cli_parse_args=False,
            sortino_from=date(2020, 1, 1),
            sortino_to=date(2019, 1, 1),
        )
