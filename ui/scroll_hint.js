// @ts-check
// Touch devices show no scrollbar, so a `.table-wrap` whose columns overflow to
// the right gets `overflow-right`, and style.css fades its right edge (#417).
// The class is set only while columns are hidden to the right: it drops when the
// table fits or is scrolled to the end.

/** @param {HTMLElement} wrap */
function update(wrap) {
  const hiddenRight = wrap.scrollWidth - wrap.clientWidth - wrap.scrollLeft;
  wrap.classList.toggle("overflow-right", hiddenRight > 1);
}

/**
 * Keep `wrap`'s `overflow-right` class in sync with its horizontal overflow.
 * Observes the wrapper and its table, so view toggles and late renders update it.
 *
 * @param {HTMLElement} wrap
 */
export function observeScrollHint(wrap) {
  const observer = new ResizeObserver(() => update(wrap));
  observer.observe(wrap);
  if (wrap.firstElementChild) observer.observe(wrap.firstElementChild);
  wrap.addEventListener("scroll", () => update(wrap), { passive: true });
  update(wrap);
}
