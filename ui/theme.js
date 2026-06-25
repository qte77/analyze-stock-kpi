// EyeRest theme toggle — system/light/dark cycle, persisted to localStorage and
// applied as data-theme on <html>. Mirrors qte77.github.io/assets/theme.js (and the
// sibling paperverse / agentic-job-offer-to-application-kit dashboards). Dispatches a
// "themechange" event so charts.js rebuilds Chart.js, which caches CSS-variable colors
// at construction time. The current mode is a dynamic aria-label; each change is
// announced via the #theme-status polite live region (a focused button's changed label
// is not re-read). Precedence on load: ?theme= URL param, then localStorage, then system.
(function () {
  var root = document.documentElement;
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;

  var ORDER = ["system", "light", "dark"];
  var WORD = { system: "System", light: "Light", dark: "Dark" };
  var GLYPH = { system: "◐", light: "○", dark: "●" };

  function initial() {
    try {
      var u = new URLSearchParams(location.search).get("theme");
      if (u === "light" || u === "dark" || u === "system") return u;
      var t = localStorage.getItem("qte77-theme");
      if (t === "light" || t === "dark") return t;
    } catch {
      /* private mode / blocked storage — fall back to system */
    }
    return "system";
  }

  var mode = initial();

  function apply(m) {
    if (m === "light" || m === "dark") root.setAttribute("data-theme", m);
    else root.removeAttribute("data-theme");
    try {
      if (m === "system") localStorage.removeItem("qte77-theme");
      else localStorage.setItem("qte77-theme", m);
    } catch {
      /* non-fatal */
    }
    btn.textContent = GLYPH[m] + " " + WORD[m];
    btn.setAttribute("aria-label", "Color theme: " + WORD[m] + " (click to change)");
    btn.title = "Color theme: " + WORD[m];
    document.dispatchEvent(new CustomEvent("themechange", { detail: { mode: m } }));
  }

  apply(mode);

  btn.addEventListener("click", function () {
    mode = ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length];
    apply(mode);
    // Announce the new mode — focus stays on the button, so the changed aria-label
    // alone is not re-read; the polite live region carries the update.
    var status = document.getElementById("theme-status");
    if (status) status.textContent = "Theme set to " + WORD[mode];
  });
})();
