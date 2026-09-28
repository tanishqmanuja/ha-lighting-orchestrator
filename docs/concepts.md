# Concepts

## Area

One HALO entry per area you care about. Usually that is a Home Assistant
area, but any key works. Each area owns its moods, its selects, and its
sensors, and areas never step on each other.

## Mood

A high-level scene for an area: `evening`, `movie`, `party`. Moods are
just names. What they actually do is defined entirely by their presets.

## Preset

A concrete variant of a mood that points at something runnable: any
`scene.*` or `script.*` entity. Each mood keeps its own preset list with
at least one entry:

- `base = scene.living_evening_base`
- `bright = script.living_boost`

Preset names are free-form, and moods don't have to share the same set.

## Default preset

The preset a bare mood request falls back to. You set it per mood.
`base` is the usual choice, but designating `party` pivots the whole
mood. When no preset is given, HALO tries your pick first, then `base`,
then a legacy `default`, then whatever comes first.

## Requested vs active

Two selects are the only things you can write to
(`select.halo_<area>_mood`, `select.halo_<area>_preset`). Everything else
just reports what is true right now:

- `sensor.halo_<area>_active_mood` / `_active_preset`: what the lights
  currently match, or `custom` if they match nothing HALO knows.
- `sensor.halo_<area>_status`: one of three states.
  - `active`: the lights match a known mood, requested or otherwise.
  - `transitioning`: a request is still in flight, inside its settle window.
  - `custom`: nothing matches, so somebody changed lights outside HALO.
     The engine never rewrites your selects over this. It only reports.
- `sensor.halo_<area>_approximated_mood`: nearest mood by 0-100
  state-first `confidence` (on/off agreement outweighs all attributes).
  Mirrors active when a known scene matches; when active is
  `custom` the highest-scoring mood wins, or `custom` again when nothing
  reaches 50.

The status sensor also carries `mismatched_entities`, the full `mapping`
of mood to preset to action, `default_presets`, and `area_name`.
