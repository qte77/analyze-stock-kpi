### Added

- **CNN F&G historical backfill via `whit3rabbit/fear-greed-data` mirror (#164).** Operator-only one-shot (`scripts/backfill_fear_greed_whitrabbit.py`, pinned to upstream SHA `aa4f6009`) extends the dashboard's long-term context from ~13 months back to 2011-01-03. Subindicators stay `null` for backfilled rows. ADR-0005 amendment classifies whit3rabbit as Tier-0.
