// @ts-check
// Data-branch base-URL resolver for the demo dashboard.
//
// Each GitHub Pages deployment should fetch ITS OWN `data` branch, so a fork
// that enables Pages renders its own data without editing the URL or always
// appending `?base=`. The base is derived from the Pages origin; non-Pages
// origins (localhost, user/org-root Pages, custom domains) fall back to the
// canonical qte77 branch.
//
// Pure module — no DOM, no side effects. Tested by tests/data.test.mjs.

const CANONICAL = "https://raw.githubusercontent.com/qte77/analyze-stock-kpi/data";

/**
 * Default data-branch base URL for a deployment, derived from its Pages origin.
 *
 * Project Pages (`<owner>.github.io/<repo>`) → that owner/repo's `data` branch
 * (so forks self-host). Anything else — `localhost`, a `<user>.github.io` root
 * site with no repo segment, or a custom domain — falls back to the canonical
 * qte77 branch. The qte77 deploy resolves to exactly `CANONICAL`, so behaviour
 * there is unchanged.
 *
 * @param {string} hostname  e.g. `location.hostname`
 * @param {string} pathname  e.g. `location.pathname`
 * @returns {string} raw.githubusercontent base (no trailing slash)
 */
export function defaultDataBase(hostname, pathname) {
  const owner = /^([^.]+)\.github\.io$/.exec(hostname);
  const repo = pathname.split("/").filter(Boolean)[0];
  return owner && repo ? `https://raw.githubusercontent.com/${owner[1]}/${repo}/data` : CANONICAL;
}
