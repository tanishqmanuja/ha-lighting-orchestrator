# Development

## Layout

- `custom_components/halo/` — the integration (`engine.py` state machine,
  `matcher.py` comparison, HA glue, `frontend/halo-panel.js` built bundle,
  `brand/` icons).
- `frontend/` — React + TypeScript + Vite panel source (Bun toolchain).
- `tests/` — pytest suite, HA-free by design.
- `.development/` — git-ignored local Docker rig (never committed).

## Checks

```sh
python -m pytest tests/ -q        # 50+ unit tests
cd frontend && bun run test       # vitest + happy-dom panel tests
cd frontend && bun run build      # tsc + bundle -> custom_components/.../halo-panel.js
```

Use `bun run <script>`, not bare `bun test` (that's Bun's own runner).

## Dev stack

`cd .development && docker compose -f compose.yaml up -d` boots HA
(:8124) + Mosquitto with optimistic MQTT discovery lights. Scripts:

- `provision_discovery.py` — retained discovery configs for dummy lights.
- `e2e_setup_moods.py`, `e2e_full.py`, `e2e_rapid.py`, `e2e_ws.py` —
  headless end-to-end (onboarding → broker → entry → apply loops).
- `check_logs.py` — fails on Traceback/ERROR in the current boot.

## Conventions

Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`),
atomic and verified: unit suite green before every commit, E2E before
behavioral changes.
