// Verified-commit helper for workflows that write to the `data` branch.
//
// All workflows hitting `data` (demo-snapshot, federal-contractors-refresh)
// route their commit through here so the retry + Blob/Tree/Commit/Ref
// pattern lives in exactly one place. Invoked from `actions/github-script@v9`:
//
//   - uses: actions/github-script@<sha>
//     env:
//       PATH_A: ${{ steps.prep.outputs.a }}
//       PATH_B: ${{ steps.prep.outputs.b }}
//     with:
//       script: |
//         const { run } = require('./scripts/data-branch-commit.cjs');
//         return run({
//           github, context, core,
//           paths: [process.env.PATH_A, process.env.PATH_B],
//           message: 'chore(demo): weekly snapshot foo',
//         });
//
// The retry handles the concurrency race exposed by demo-snapshot's
// matrix (#130 / #132): N matrix legs all read the same parent SHA,
// the leg that races last on updateRef sees `422 Reference cannot be
// updated` because the ref moved between getRef and updateRef. Blobs
// are content-addressed and persist across retries; only the tree +
// commit + ref-update are recomputed.

"use strict";

const fs = require("fs");

const MAX_ATTEMPTS = 8;

/**
 * @param {object} args
 * @param {import('@octokit/core').Octokit} args.github
 * @param {{repo: {owner: string, repo: string}}} args.context
 * @param {{info: (msg: string) => void}} args.core
 * @param {string[]} args.paths   Filesystem paths to commit (relative to repo root).
 * @param {string} args.message   Commit message.
 * @param {string} [args.branch]  Target branch (default "data").
 */
async function run({ github, context, core, paths, message, branch = "data" }) {
  const { owner, repo } = context.repo;

  const mkBlob = async (path) => {
    const content = fs.readFileSync(path).toString("base64");
    const blob = await github.rest.git.createBlob({
      owner, repo, content, encoding: "base64",
    });
    return { path, mode: "100644", type: "blob", sha: blob.data.sha };
  };
  const tree = await Promise.all(paths.map(mkBlob));

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const ref = await github.rest.git.getRef({
        owner, repo, ref: `heads/${branch}`,
      });
      const parentSha = ref.data.object.sha;
      const parentCommit = await github.rest.git.getCommit({
        owner, repo, commit_sha: parentSha,
      });
      const newTree = await github.rest.git.createTree({
        owner, repo, base_tree: parentCommit.data.tree.sha, tree,
      });
      const commit = await github.rest.git.createCommit({
        owner, repo, message, tree: newTree.data.sha, parents: [parentSha],
      });
      await github.rest.git.updateRef({
        owner, repo, ref: `heads/${branch}`, sha: commit.data.sha,
      });
      core.info(
        `Created verified commit ${commit.data.sha.slice(0, 8)} ` +
        `on ${branch} (attempt ${attempt}/${MAX_ATTEMPTS})`,
      );
      return;
    } catch (err) {
      if (err.status === 422 && attempt < MAX_ATTEMPTS) {
        const backoff = 500 * attempt + Math.floor(Math.random() * 500);
        core.info(
          `Ref update lost race (attempt ${attempt}/${MAX_ATTEMPTS}); ` +
          `retrying in ${backoff}ms`,
        );
        await new Promise((r) => setTimeout(r, backoff));
        continue;
      }
      throw err;
    }
  }
}

module.exports = { run };
