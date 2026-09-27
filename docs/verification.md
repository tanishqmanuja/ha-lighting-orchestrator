# Verification

HALO closes the loop most lighting setups leave open: apply, wait,
compare, report. Four per-mood timings plus one rule per preset decide
how strict that loop is.

## Timings

- **Transition (s):** the fade time handed to the scene (`transition`) or
  the script (`transition_time`). Start with 1 to 2 seconds. Long
  architectural fades can use 10 to 30.
- **Settle (s):** grace period right after applying. Status reads
  `transitioning` and nothing gets judged yet, so slow fades and mesh
  lag don't look like failure. A good rule is settle of at least
  transition plus 2. If a mood flips to `custom` the moment you apply
  it, raise settle first.
- **Debounce (s):** quiet wait after one of the tracked lights changes
  before HALO re-checks. One physical change often arrives as several
  events (brightness, then color, then temperature), and without this
  the status flickers between `active` and `custom`. Start with 1 to 2.
- **Tolerance (±):** how close counts as matching, measured in
  brightness points and degrees. A value of 1 absorbs rounding (the
  scene says 128, the light reports 127). Raise it for chatty dimmers,
  keep it tight for exact color scenes.

## Verify modes (per preset)

- **Recommended (auto):** scenes get checked against their own
  `scenes.yaml` targets, and scripts are trusted once applied.
- **Snapshot on apply:** after the settle window, HALO snapshots what
  the lights actually show and compares against that snapshot from then
  on. Suits deterministic scripts. Just know a failed first apply
  teaches a wrong snapshot. Resync re-teaches it.
- **Trust apply:** past settle, the preset reports `active` without any
  comparison. Built for dynamic scripts with delays, randomness, or
  conditionals. The tradeoff is real: manual drift can't be detected in
  this mode.
- **Same scene:** one-click version of a self-reference, for scene actions.
- **Reference scene:** verify a script's result against another scene's
  targets. You get a free-form action with a strict check.

Scene targets come straight from `scenes.yaml`, compared attribute by
attribute with your tolerance and ignore rules. Script snapshots are
learned on first apply and stored per area.
