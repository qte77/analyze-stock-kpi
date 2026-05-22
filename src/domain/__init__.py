"""Domain primitives — universe resolution + composite scoring.

These modules hold the project's domain logic (what to compute and
how it's keyed), independent of where the underlying data comes from.
Data fetched via :mod:`src.data_sources` flows through these
primitives to produce the snapshots and scores rendered by
:mod:`src.__main__`.
"""
