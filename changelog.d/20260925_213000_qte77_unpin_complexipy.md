### Changed

- Unpinned `complexipy` (5.5.0 → `>=8.0.1`). Since 6.x it also scores comprehensions, which put
  11 unchanged functions over the gate of 10; they are recorded in `complexipy-snapshot.json`,
  so the gate stays at 10 for everything else and fails if any recorded function gets worse.
