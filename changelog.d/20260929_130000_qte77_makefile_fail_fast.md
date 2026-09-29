### Fixed

- `make validate` (and every other multi-line make target) now fails on the first failing
  command. With `.ONESHELL` and no `-e`, only a recipe's last command counted, so `lint_js`
  silently ignored TypeScript and ESLint errors and `make validate` reported success.
