# Configuration reference

Everything below lives per area, editable in the panel's Manage page or
the entry's Configure dialog (same store).

## Add entry

Pick the HA area (or a custom key), a friendly name, and a comma-separated
mood list. Fresh moods start with one unmapped `base` preset.

## Per mood

- **Presets** (`base=scene.x, party=script.y@off`, at least one) —
  comma-separated `name=action` pairs. The optional `@verify` suffix sets
  the verify mode inline: `@off`, `@snapshot`, or `@scene.<id>`
  (example above: the party preset trusts its script).
- **Default preset** — must name one of the presets.
- **Post script** (optional `script.*`) — runs once when the requested
  mood verifies as current. See [Automations](automations.md).
- **Tracked entities** (empty = auto) — which lights to verify. Empty
  resolves from `scenes.yaml` for scenes; the editor's Autofill drafts
  that set for editing.
- **Transition / Settle / Debounce / Tolerance** — see
  [Verification](verification.md).
- **Ignored attributes** — skipped in comparisons (e.g. `effect`).
- **Ignore unavailable** — treat missing entities as unknown, not as
  mismatches.

Validation is strict: unknown presets, bad entity ids, and bad verify
values are rejected with messages instead of saved silently.
