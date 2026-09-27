# Troubleshooting

## Stuck on `custom` right after applying

Your settle window is shorter than the fade. Raise **settle** above
`transition + 2` for that mood and try again.

## Status flickers between `active` and `custom`

One physical change arrives as several events. Raise **debounce** to 2
or 3 seconds so HALO waits for the dust to settle before judging.

## Never reaches `active`, with mismatches listed

- Brightness off by a few points: raise **tolerance**.
- An attribute the device reports unreliably: add it to **ignore attrs**.
- A scene was renamed: re-check the preset mapping. Autofill shows what
  the scene actually addresses.
- Script presets: make sure the verify mode fits. Deterministic scripts
  want **Snapshot**, dynamic ones want **Trust apply**.

## Panel shows stale content or stays blank

Hard-refresh once (`Ctrl+Shift+R`). The bundle URL carries the
integration version, so updates propagate on their own. With devtools
open (F12), look for `[halo-panel] loaded`. A missing line means the
bundle never arrived. Anything after it is a render error, so report it
with the message.

## Entry changes don't seem to apply

Option writes reload the entry within a few seconds. If the sensors
look stale, reload the integration or restart Home Assistant. One
gotcha: HA entry reloads don't re-import Python modules, so code
changes always need a full restart.

## Logs

Set `custom_components.halo: debug` under `logger:` to see engine
decisions, learn events, and post-script runs.
