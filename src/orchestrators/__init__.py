"""Orchestrators — multi-source pipelines that combine data sources + domain logic.

Each orchestrator chains :mod:`src.data_sources` calls through
:mod:`src.domain` primitives to produce a higher-order artifact
(e.g. the federal-contractors universe preset + audit trail).
"""
