# Panel

The sidebar **HALO** page (`/halo`, with per-area sub-routes like
`#/manage/living_room/evening`) mirrors the entities but adds what native
HA cannot: which scene/script each preset runs, drift lists, one-click
resync, and full mapping management.

## Area cards

- Mood and preset pickers (the single source of input), requested-vs-active
  readout, and a status badge (`active` / `transitioning` / `custom`).
- Every preset button shows the scene/script it triggers, with a `Default`
  marker on the designated default.
- Manual drift appears as a "Manual changes detected" list. **Resync**
  re-applies the request; **Resync all** (header) covers every area.
- The active preset carries no Apply button — there is nothing to apply.

## Manage page

Per-card **Manage** opens a full-page editor for that area: mood sidebar
with preset counts, and a form per mood (presets with a Scene/Script
toggle, default picker, tracked entities with Autofill-from-scenes,
timings, ignores, post script). Saving writes the entry options, which
auto-reload the area. A footer explains the verification timings.

The header also links to **Configure** (the classic options dialog —
same store, either editor works).

## Notes

- The bundle URL is version-pinned (`halo-panel.js?v=x.y.z`), so updates
  arrive without manual cache clearing — one hard refresh at most.
- If the page ever stays blank, open devtools (F12): the bundle logs
  `[halo-panel] loaded` on success, and anything after it points at the
  cause.
