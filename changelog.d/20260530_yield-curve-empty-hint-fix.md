### Fixed

- **Demo: 5s10s slope tab stuck on `loading…` when no history yet.** The lazy-render path overwrote the existing `.yc-empty` element instead of skipping when one was already there.
- **Demo: unified the empty-history label.** F&G rolling / F&G long-term / 5s10s slope all now read `no history yet` (was three different strings).
