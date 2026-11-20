### Security

- `demo-snapshot.yaml` and `universe-builder.yaml` grant `GITHUB_TOKEN` permissions per job instead of at the
  workflow level: the matrix jobs get read or nothing; only the jobs that commit or open PRs get write.
- `universe-builder.yaml` no longer uses the `workflow_run` trigger. `demo-snapshot.yaml` now calls it as its
  last job (`workflow_call`), on `main` only, after every snapshot leg has succeeded, so the ordering and
  the skip-on-failure guard are unchanged.
