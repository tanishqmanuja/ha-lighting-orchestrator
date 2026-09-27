# HALO panel frontend (React + Vite, run with Bun)

Source of the HA sidebar panel. The built bundle is committed at
`../custom_components/halo/frontend/halo-panel.js` (HA serves only that
file, so styles are inlined into the JS — see `src/main.tsx`).

Requires [Bun](https://bun.sh) 1.x.

```sh
bun install        # install deps (commits bun.lock)
bun run test       # vitest unit tests (halo.ts helpers)
bun run build      # tsc + vite build -> ../custom_components/halo/frontend/
```

> NOTE: use `bun run test`, not bare `bun test` — the latter invokes Bun's
> own test runner instead of the vitest suite.

Stack: React 18 + Vite + TypeScript, [@tanstack/react-form](https://tanstack.com/form)
for editor validation (every input validates as you type; cross-field rules
run on submit), [sonner](https://sonner.emilkowal.ski/) for save/delete
toasts. Sonner's CSS is inlined into the bundle (`?inline` import) because
HA mounts panels inside shadow DOM, which `document.head` styles cannot
pierce — same reason our own stylesheet rides inside the React tree.

Layout:

- `src/main.tsx` — `<halo-panel>` custom-element bridge (HA assigns `.hass`)
- `src/App.tsx` — area grid + empty state
- `src/components/AreaCard.tsx` — mood/preset pickers, status, drift, resync
- `src/components/OptionButtons.tsx`, `StatusBadge.tsx` — presentational
- `src/halo.ts` — pure, tested helpers (entity ids, area discovery, status)
- `src/ha-types.ts` — minimal HA frontend types

After rebuilding, hard-refresh the HA panel (or bump the file) — browsers
cache `/halo_static/halo-panel.js` aggressively.
