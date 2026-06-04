### Changed

- **Aggregator derives composite-field list from `CompositeScores.model_fields`.** `src/orchestrators/aggregated_scores_best_and_worst.py` previously hardcoded the 7-field tuple in two places (the model definition and the orchestrator constant); adding a new composite would have been silently omitted from cross-universe ranking. Now the tuple is `tuple(CompositeScores.model_fields)` — single source of truth, zero hidden coupling. Regression guard added in `tests/test_aggregated_scores_best_and_worst.py`.
