# Verification

HALO closes the loop: apply → wait → compare → report. Four per-mood
timings plus one rule per preset control how strict that loop is.

## Timings

- **Transition (s)** — fade time handed to the scene (`transition`) or
  script (`transition_time`). Start with `1–2`; architectural fades can
  use `10–30`.
- **Settle (s)** — grace period after applying. Status shows
  `transitioning` and nothing is judged yet, so slow fades and mesh
  latency don't read as failure. Rule of thumb: `settle ≥ transition + 2`.
  If a mood flips to `custom` right after applying, raise settle.
- **Debounce (s)** — quiet wait after a member light changes before
  re-checking. Absorbs multi-attribute updates (brightness, then color,
  then temperature arriving as separate events) so one physical change
  doesn't flicker `active → custom → active`. Start with `1–2`.
- **Tolerance (±)** — how close counts as matching, in brightness points
  and degrees. `1` absorbs rounding (scene says 128, light reports 127);
  raise it for chatty dimmers, keep it tight for exact color scenes.

## Verify modes (per preset)

- **Recommended (auto)** — scenes are checked against their own
  `scenes.yaml` targets; scripts are trusted once applied.
- **Snapshot on apply** — after the settle window, snapshot what the
  lights actually show and compare against that from then on. For
  deterministic scripts. A failed first apply teaches a wrong snapshot —
  Resync re-teaches.
- **Trust apply** — past settle, report `active` without comparing.
  For dynamic scripts (delays, randomness, conditionals). Manual drift is
  not detectable in this mode.
- **Same scene** — one-click version of a self-reference for scene actions.
- **Reference scene** — verify a script's *outcome* against another
  scene's targets. Free-form action, strict check.

Scene targets are read from `scenes.yaml` (exact compare on stored
attributes only, honoring tolerance/ignore rules). Script snapshots are
learned and persisted per area.
