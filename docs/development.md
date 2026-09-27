# Development

## Layout

- `custom_components/halo/` holds the integration: the `engine.py`
  state machine, the `matcher.py` comparison, the HA glue, the built
  `frontend/halo-panel.js` bundle, and the `brand/` icons.
- `frontend/` is the React + TypeScript + Vite panel source, built with
  the Bun toolchain.
- `tests/` is the pytest suite, HA-free by design.
- `.development/` is a git-ignored local Docker rig. It is never committed.

## Checks

```sh
python -m pytest tests/ -q        # 50+ unit tests
cd frontend && bun run test       # vitest + happy-dom panel tests
cd frontend && bun run build      # tsc + bundle into custom_components/.../halo-panel.js
```

Run scripts with `bun run <name>`. Bare `bun test` invokes Bun's own
runner instead of the vitest suite.

## Dev stack

`cd .development && docker compose -f compose.yaml up -d` boots Home
Assistant (:8124) plus Mosquitto with optimistic MQTT discovery lights.
Useful scripts in there:

- `provision_discovery.py` writes retained discovery configs for dummy lights.
- `e2e_setup_moods.py`, `e2e_full.py`, `e2e_rapid.py`, `e2e_ws.py` run
  the whole loop headlessly, from onboarding to apply cycles.
- `check_logs.py` fails on Traceback/ERROR in the current boot.

## Conventions

Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`),
kept atomic and verified: green unit suite before every commit, full
E2E before behavioral changes.
