"""Orchestrators — multi-source pipelines that combine data sources + domain logic.

Each orchestrator chains :mod:`analyze_stock_kpi.data_sources` calls through
:mod:`analyze_stock_kpi.domain` primitives to produce a higher-order artifact
(e.g. the federal-contractors universe preset + audit trail).
"""
