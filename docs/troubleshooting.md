# Troubleshooting

## Stuck on `custom` right after applying

The settle window is shorter than the fade. Raise **settle** above
`transition + 2` for that mood.

## Status flickers `active → custom → active`

One physical change arrives as several events. Raise **debounce** to
`2–3` seconds.

## Never reaches `active`, mismatches listed

- Brightness off by a few points → raise **tolerance**.
- An attribute the device reports unreliably → add it to **ignore attrs**.
- A scene was renamed → re-check the preset mapping (Autofill shows what
  the scene actually addresses).
- Script presets: confirm the verify mode fits (deterministic →
  **Snapshot**, dynamic → **Trust apply**).

## Panel shows stale content or stays blank

Hard-refresh once (`Ctrl+Shift+R`). The bundle URL is version-pinned, so
updates propagate on their own. With devtools open (F12), look for
`[halo-panel] loaded`: absent means the bundle never arrived; anything
after it is a render error — report it with the message.

## Entry changes don't seem to apply

Options writes auto-reload the entry (a few seconds). If sensors look
stale, reload the integration or restart HA. HA entry reloads don't
re-import Python modules — code changes always need a restart.

## Logs

Set `custom_components.halo: debug` under `logger:` for engine decisions,
learn events, and post-script runs.
