<picture align="center">
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/halo/brand/dark_logo.png">
  <img src="custom_components/halo/brand/logo.png" width="160" alt="HALO logo">
</picture>

# HALO // Home Assistant Lighting Orchestrator

Most lighting automations are fire-and-forget: they call a scene and hope
the room followed along. HALO works the other way. You pick a mood for an
area, HALO runs your scenes or scripts, waits for the lights to settle,
then actually checks they match. The dashboard tells you the result:
`active`, still `transitioning`, or overridden by hand (`custom`).

- One place to ask: two selects per area, everything else is read-only.
- Proof instead of optimism: per-mood tolerance, settle, debounce, and mismatch reporting.
- Your own scenes and scripts: every preset points at any `scene.*` or `script.*`, with its own verification mode.
- A sidebar panel that feels like the rest of Home Assistant: area cards, live status, and mapping management right on the page.

## 📦 Installation

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

## 🚀 Quick start

1. Add an entry per area: pick the HA area, list its moods (for example `evening, movie`).
2. Map each mood: open the sidebar **HALO** page, hit **Manage** on the area card (the entry's Configure dialog edits the same settings). A typical preset looks like `base = scene.living_evening_base`. Choose which preset is the default.
3. Pick a mood on the card (or through the `select.halo_<area>_mood` entity). The status reads `transitioning`, then flips to `active` once the lights check out.
4. Dim a light by hand and watch the status flip to `custom`, naming the drifted entity. **Resync** puts the requested mood back.

## 📚 Docs

- [Concepts](docs/concepts.md): areas, moods, presets, requested vs active.
- [Verification](docs/verification.md): transition, settle, debounce, tolerance, verify modes.
- [Panel](docs/panel.md): sidebar UI, Manage page, routes.
- [Configuration](docs/configuration.md): options-flow reference.
- [Automations](docs/automations.md): services, events, YAML examples, post scripts.
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md): tests, dev stack, frontend build.

## 🙏 Inspiration

Special thanks to these awesome projects. HALO stands on their ideas:

- [hass_mood_controller](https://github.com/ZeFish/hass_mood_controller) by ZeFish: the moods-and-presets hierarchy and central dispatch this engine grew out of.
- [stateful_scenes](https://github.com/hugobloem/stateful_scenes) by hugobloem: tolerance, debounce, and transition-aware scene matching.
- [scene_state](https://github.com/pszypowicz/scene_state) by pszypowicz: grace periods, binary active tracking, and mismatch reporting.

## 🍀 Show Your Support

Give a ⭐️ if this project helped you!
