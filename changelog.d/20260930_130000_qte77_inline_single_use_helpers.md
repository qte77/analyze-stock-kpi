### Removed

- Two helper modules that only existed to share code with the retired screener (#413) are
  folded into their single remaining user: `orchestrators/_shared.py` into
  `aggregated_scores_best_and_worst.py`, and `scripts/_demo_snapshot_loader.py` into
  `scripts/build_aggregated_scores_best_and_worst.py`. No behaviour change: the rebuilt
  best/worst 25 match the committed presets exactly on the 2026-09-27 data.
