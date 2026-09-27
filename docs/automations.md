# Automations

## Services

- `halo.apply_mood` — `{area?, mood, preset?, homewide?}`. Omitting
  `preset` resolves the mood's default. With `homewide: true`, locked
  areas are skipped.
- `halo.resync` — `{area?}` re-applies the current request (clears
  manual `custom` drift). Omit `area` for all areas.

```yaml
# Movie time: lock the room, dim it, unlock + resync after
- service: halo.apply_mood
  data:
    area: living_room
    mood: movie
```

## Events

- `halo_mood_applied` — `{area, mood, preset, seq}` on every request.
- `halo_active_changed` — `{area, active_mood, active_preset, status,
  mismatched}` whenever the verdict changes.
- `halo_post_action` — `{area, mood, preset, script}` after a post
  script runs.

## Post scripts

An optional per-mood `script.*` that runs **once per request**, right
after the transition verifies as current — never on background
re-evaluations, even across quick successive requests (sequence-guarded).
Failures are logged without touching the status. Typical uses: close
blinds, start music, notify. Set it in Manage (Post script) or the
dialog.

## Locking

Set a per-area `input_boolean` lock (options) to shield a room from
home-wide applies. Direct single-area requests still go through, so
in-room controls keep working.
