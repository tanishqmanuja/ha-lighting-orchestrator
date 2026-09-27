# Panel

The sidebar **HALO** page (`/halo`, with per-area sub-routes like
`#/manage/living_room/evening`) shows the same entities you'd find in
Developer Tools, plus the things native HA can't show: which
scene/script each preset runs, drift lists, one-click resync, and full
mapping management.

## Area cards

- Mood and preset pickers. These are the single source of input.
- Requested-vs-active readout plus a status badge (`active`,
  `transitioning`, or `custom`).
- Every preset button names the scene or script it runs, with a
  `Default` marker on the designated default.
- Manual drift shows up as a "Manual changes detected" list.
  **Resync** re-applies the request, and **Resync all** in the header
  covers every area.
- The active preset has no Apply button. There is nothing to apply.

## Manage page

Each card's **Manage** button opens a full-page editor for that area: a
mood sidebar with preset counts on the left, and the form on the right
(presets with a Scene/Script toggle, default picker, tracked entities
with Autofill-from-scenes, timings, ignores, post script). Saving writes
the entry options, which reload the area on their own. A footer at the
bottom explains the verification timings in plain language.

The header also links to **Configure**, the classic options dialog. Both
editors write to the same place, so use whichever you prefer.

## Notes

- The bundle URL carries the integration version
  (`halo-panel.js?v=x.y.z`), so updates arrive without manual cache
  clearing. One hard refresh at most.
- If the page ever stays blank, open devtools (F12) and look for
  `[halo-panel] loaded` in the console. If that line is missing, the
  bundle never arrived. If it is there, whatever follows it is the
  render error, so report it with the message.
