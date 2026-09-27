# Configuration reference

Everything here lives per area. Edit it in the panel's Manage page or in
the entry's Configure dialog. Both write to the same store.

## Add entry

Pick the HA area (or a custom key), give it a friendly name, and list
its moods separated by commas. Fresh moods start with one unmapped
`base` preset.

## Per mood

- **Presets** (at least one, e.g. `base=scene.x, party=script.y@off`):
  comma-separated `name=action` pairs. The optional `@verify` suffix
  sets the verify mode inline (`@off`, `@snapshot`, or `@scene.<id>`).
  The example above makes the party preset trust its script.
- **Default preset:** has to name one of the presets above.
- **Post script** (optional `script.*`): runs once when the requested
  mood verifies as current.
- **Tracked entities** (empty means auto): which lights get verified.
  Left empty, scenes resolve from `scenes.yaml` automatically. The
  editor's Autofill drafts that set so you can tweak it by hand.
- **Transition / Settle / Debounce / Tolerance:** covered in
  [Verification](verification.md).
- **Ignored attributes:** skipped in comparisons (handy for `effect` and
  the like).
- **Ignore unavailable:** treats missing entities as unknown instead of
  counting them as mismatches.

Validation is strict on purpose. Unknown presets, bad entity ids, and
bad verify values get rejected with a message instead of being saved
quietly.
