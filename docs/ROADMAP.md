# Roadmap

**Pending work only.** For what has already shipped, see
[`RELEASES.md`](RELEASES.md); for the full commit history, `git log`.

Everything that could be finished from the Windows development machine has been.

---

## Ongoing, not blocked

Nothing else is queued that can be checked from here. Two things stay manual by design:

- **New Windows apps** found only in the Start Menu are added by hand to `tools/data/vendor_apps.json`
  (then `tools/icons/backfill.py` ships their icons).
- **Icon coverage**: 136 of 440 entries have no shipped icon, almost all Linux-only or macOS-only apps that
  aren't installed on the machine the icons are collected from. On Windows the runtime fallback fills the
  gaps for anything installed.

## Testing

Unit coverage runs in CI on every push: `cargo test` (all three OSes), the Python catalog/scan tests
(`tools/tests/test_tools.py`), and the jsdom frontend tests (`tools/tests/frontend`).
