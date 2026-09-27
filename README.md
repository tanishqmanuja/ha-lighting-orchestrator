# HALO — Home Assistant Lighting Orchestrator

One input per area. Verified states, never assumed ones.

HALO gives every area **moods** (evening, movie, party…) each with its own
**presets** (base, bright…). You pick a mood; HALO runs your scenes or
scripts, waits for the lights to settle, then *checks* they actually match —
and tells you whether the mood is `active`, still `transitioning`, or was
overridden by hand (`custom`).

- 🎯 **Single source of input** — two selects per area, everything else is read-only truth.
- ✅ **Verified, not optimistic** — per-mood tolerance, settle, debounce and mismatch reporting.
- 🧩 **Your scenes and scripts** — each preset maps to any `scene.*` or `script.*`, with per-preset verification modes.
- 🖥️ **Sidebar panel** — area cards, live status, and in-page mapping management that looks like native Home Assistant.

## Installation

1. Install via HACS (custom repository) or copy `custom_components/halo` to `<config>/custom_components/halo`.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **HALO**.

Requires Home Assistant 2026.3+ (local brand images).

## Quick start

1. Add an entry per area: pick the HA area, list its moods (e.g. `evening, movie`).
2. Map each mood: sidebar **HALO** → **Manage** on the area card (or the entry's Configure). Example preset: `base = scene.living_evening_base`. Pick which preset is the default.
3. Pick a mood on the card (or the `select.halo_<area>_mood` entity). Status goes `transitioning`, then `active` once verified.
4. Dim a light by hand: status flips to `custom` and names the drifted entity. **Resync** re-applies.

## Docs

- [Concepts](docs/concepts.md) — areas, moods, presets, requested vs active.
- [Verification](docs/verification.md) — transition, settle, debounce, tolerance, verify modes.
- [Panel](docs/panel.md) — sidebar UI, Manage page, routes.
- [Configuration](docs/configuration.md) — options-flow reference.
- [Automations](docs/automations.md) — services, events, YAML examples, post scripts.
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md) — tests, dev stack, frontend build.

MIT licensed. Issues and PRs welcome.
