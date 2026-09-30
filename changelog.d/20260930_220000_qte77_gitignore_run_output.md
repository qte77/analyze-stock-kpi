### Fixed

- `.gitignore` covers `make run`'s current output path, `results/fundamentals/<timestamp>.json`
  (only the old flat name `results/fundamentals_*.json` was ignored), so local runs can't be
  committed by accident.
