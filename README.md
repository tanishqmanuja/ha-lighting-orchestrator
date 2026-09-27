# HALO: Home Assistant Lighting Orchestrator

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=halo)

Most lighting automations are fire-and-forget: they call a scene and hope
the room followed along. HALO works the other way. You pick a mood for an
area, HALO runs your scenes or scripts, waits for the lights to settle,
then actually checks they match. The dashboard tells you the result:
`active`, still `transitioning`, or overridden by hand (`custom`).

- One place to ask: two selects per area, everything else is read-only.
- Proof instead of optimism: per-mood tolerance, settle, debounce, and mismatch reporting.
- Your own scenes and scripts: every preset points at any `scene.*` or `script.*`, with its own verification mode.
- A sidebar panel that feels like the rest of Home Assistant: area cards, live status, and mapping management right on the page.

## Installation

### HACS

Install via [HACS](https://hacs.xyz) by searching for
`ha-lighting-orchestrator` in the integrations section, or simply click
the button below. If search doesn't find it yet, add the repository URL
as a custom repository in HACS first.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tanishqmanuja&repository=ha-lighting-orchestrator&category=integration)

### Manual

Clone the repository and copy the `custom_components` folder to your
Home Assistant config folder, then restart:

```sh
git clone https://github.com/tanishqmanuja/ha-lighting-orchestrator.git
cp -r ha-lighting-orchestrator/custom_components config/
```

Then: Settings → Devices and Services → Add Integration → **HALO**,
or click the badge at the top of this page.

Requires Home Assistant 2026.3+ (local brand images).

## Quick start

1. Add an entry per area: pick the HA area, list its moods (for example `evening, movie`).
2. Map each mood: open the sidebar **HALO** page, hit **Manage** on the area card (the entry's Configure dialog edits the same settings). A typical preset looks like `base = scene.living_evening_base`. Choose which preset is the default.
3. Pick a mood on the card (or through the `select.halo_<area>_mood` entity). The status reads `transitioning`, then flips to `active` once the lights check out.
4. Dim a light by hand and watch the status flip to `custom`, naming the drifted entity. **Resync** puts the requested mood back.

## Docs

- [Concepts](docs/concepts.md): areas, moods, presets, requested vs active.
- [Verification](docs/verification.md): transition, settle, debounce, tolerance, verify modes.
- [Panel](docs/panel.md): sidebar UI, Manage page, routes.
- [Configuration](docs/configuration.md): options-flow reference.
- [Automations](docs/automations.md): services, events, YAML examples, post scripts.
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md): tests, dev stack, frontend build.

MIT licensed. Issues and PRs welcome.
