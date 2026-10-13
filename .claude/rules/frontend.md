---
paths:
  - "mizrahi-touch-ai-demo/frontend/**"
---

# Frontend rules (React 18 · Vite · TypeScript strict)

Locations: `mizrahi-touch-ai-demo/docs/CODEMAP.md` → Frontend.

- All HTTP goes through `src/api.ts` (`api.*` + types). Two legacy direct `fetch` calls exist (`App.tsx` fixtures,
  `ScenarioPresenter.tsx` scenarios); don't add more.
- Types in `api.ts` are hand-written copies of backend JSON. Change the backend response and `api.ts` in the same task.
- Case state comes from `useCase()` (`caseContext.tsx`) and `usePolling`. No new state, routing, UI or CSS libraries;
  no new dependencies without approval.
- Styling: the single `src/styles.css` with `--mz-*` tokens; reuse existing classes and components before adding new ones.
- RTL Hebrew: `index.html` sets `dir="rtl"`. Wrap IDs, file names and Latin/number runs in `.ltr`.
  All copy is Hebrew; use `ils`, `monthHe`, `timeHe` and the label maps in `api.ts`.
- Keep the concept-demo / synthetic-data notice visible; it is part of the product's governance.
- Banker forms send one `newRequestId()` per submission (`pages/banker/deskUi.tsx`). Identity is the server session
  (`backend/app/auth.py`); the apps obtain demo sessions themselves (`caseContext.tsx`, `BankerConsole.tsx`). Never send an
  identity header: the service ignores `X-Staff-Id`. A 401 dispatches `AUTH_EVENT` (`api.ts`) and the app re-obtains its session.
- The assistant only renders actions the server offered; resolve them through `api.resolveAction` before navigating.

## Verify a frontend change
1. `cd mizrahi-touch-ai-demo/frontend && ./node_modules/.bin/tsc --noEmit -p .`
2. `npm run build` — :8790 serves `frontend/dist`, so without a build the running app shows the old UI.
3. Look at it in a browser: customer app at phone width (~390 px) and on desktop ≥ 901 px (presenter pane),
   plus `/banker` if touched. For flows, use the `run-stack` skill (isolated backend).
