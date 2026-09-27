# Automations

## Services

- `halo.apply_mood` takes `{area?, mood, preset?, homewide?}`. Leave out
  `preset` and the mood's default is used. With `homewide: true`,
  locked areas sit the call out.
- `halo.resync` takes `{area?}` and re-applies the current request,
  which clears manual `custom` drift. Leave out `area` for everywhere.

```yaml
# Movie time: dim the room to its movie mood
- service: halo.apply_mood
  data:
    area: living_room
    mood: movie
```

## Events

- `halo_mood_applied` (`{area, mood, preset, seq}`) fires on every request.
- `halo_active_changed` (`{area, active_mood, active_preset, status,
  mismatched}`) fires whenever the verdict changes.
- `halo_post_action` (`{area, mood, preset, script}`) fires after a post
  script runs.

## Post scripts

An optional per-mood `script.*` that runs a single time per request,
right after the transition verifies as current. It never fires on
background re-evaluations, not even across quick successive requests
(the request sequence guards that). If it fails, the failure is logged
and the status is left alone. Typical uses: close blinds, start music,
send a notification. Set it in Manage (Post script) or the dialog.

## Locking

Give an area an `input_boolean` lock in its options and home-wide
applies will skip that room. Direct single-area requests still go
through, so the in-room controls keep working while the rest of the
house follows the rhythm.
