# Concepts

## Area

One HALO config entry per user-defined area (usually an HA area, but any
key works). Each area owns its moods, its selects, and its sensors. Areas
never interfere with each other.

## Mood

A high-level scene for an area: `evening`, `movie`, `party`. Moods are
just names — what they *do* is defined entirely by their presets.

## Preset

A concrete variant of a mood that maps to something runnable: any
`scene.*` or `script.*` entity. Each mood has its own preset list with at
least one entry:

- `base = scene.living_evening_base`
- `bright = script.living_boost`

Preset names are free-form per mood; nothing forces every mood to share
the same set.

## Default preset

The preset a bare mood request resolves to. Set it per mood — usually
`base`, but designating `party` pivots the whole mood. Resolution order
for an empty request: your pick → `base` → legacy `default` → first.

## Requested vs active

Two selects are the **only writable inputs** (`select.halo_<area>_mood`,
`select.halo_<area>_preset`). Everything else reports truth:

- `sensor.halo_<area>_active_mood` / `_active_preset` — what the lights
  actually match right now (or `custom`).
- `sensor.halo_<area>_status` — one of:
  - `active` — the lights match a known mood (requested or otherwise).
  - `transitioning` — a request is in flight, inside its settle window.
  - `custom` — nothing matches. Someone changed lights outside HALO.
    The engine never rewrites your selects; it only reports.

The status sensor also carries `mismatched_entities`, the full `mapping`
(mood → preset → action), `default_presets`, and `area_name`.
