# Codebase ICU — Dashboard (Block 5)

The frontend for **Codebase ICU — Explainable Autonomous Software Recovery**.
It is the product's user-facing interface: a dark, developer-tool-styled
dashboard that makes the recovery workflow —

```text
FAILURE → EVIDENCE → ROOT CAUSE → SAFE REPAIR → VERIFIED RECOVERY
```

— understandable to a hackathon judge without reading source code.

> **IBM Bob 2.0 is the AI reasoning component of Codebase ICU.** This
> dashboard does not diagnose or repair anything itself — it visualizes
> deterministic evidence produced by the Codebase ICU backend
> (`codebase-icu/backend`) and by Bob's investigation/repair.

## Purpose

One screen, one button ("RUN RECOVERY ANALYSIS"), four stages:

1. **Failure** — live test results from the target application (via the
   backend's `POST /tests/run`).
2. **Investigation** — an "IBM BOB INVESTIGATION" panel plus the confirmed
   root cause, backed by the actual commit and diff that introduced the bug
   (via `GET /repository/commits/{hash}` and `GET /repository/diff/{hash}`).
3. **Safe Repair** — the isolated repair diff, and a clear MAIN vs. SANDBOX
   comparison making it visible that `main` was never touched.
4. **Verification** — a before/after comparison table, labeled as
   "CODEBASE ICU VERIFICATION" to distinguish it from Bob's own diagnosis.

## Setup / installation

```bash
cd codebase-icu/frontend
npm install
```

## Development server

```bash
npm run dev
```

Serves the dashboard at `http://localhost:5173`.

## Backend URL configuration

The dashboard calls the Codebase ICU backend via `src/services/api.js`,
which reads `VITE_API_BASE_URL` (Vite's standard `import.meta.env`
mechanism). Copy `.env.example` to `.env.local` and edit it if the backend
isn't at the default:

```bash
# .env.local
VITE_API_BASE_URL=http://127.0.0.1:8000
```

If unset, it defaults to `http://127.0.0.1:8000`.

The backend must also allow the dashboard's origin via CORS — see
[Running the application](#running-the-application) below.

## Build

```bash
npm run build
```

Outputs a static bundle to `dist/`. `npm run preview` serves that bundle
locally to sanity-check the production build.

## Architecture

```text
frontend/
├── src/
│   ├── components/     one component per dashboard panel/stage
│   ├── services/
│   │   └── api.js       thin fetch wrapper around the backend - no
│   │                     backend logic is duplicated here
│   ├── config/
│   │   └── demo.js       clearly-labeled facts this demo's backend has no
│   │                     endpoint to discover live (see below)
│   ├── utils/            pure helpers (diff parsing, failure-reason
│   │                     parsing) with small vitest unit tests
│   ├── App.jsx           orchestrates the "Run Recovery Analysis" flow
│   ├── main.jsx          React entry point
│   └── styles.css        the entire visual design (plain CSS, no framework)
├── public/
│   └── favicon.svg
├── index.html
├── package.json
└── vite.config.js
```

### Real data vs. demo data

Nearly everything on the dashboard is fetched live from the backend at
analysis time: repository status, the target application's test results,
and both the root-cause and repair commits' metadata/diffs (Git worktrees
share one object database, so the repair commit is visible to the backend's
analyzer even though it lives on a different branch/worktree).

Two facts are **not** available through any existing backend endpoint, and
are supplied as clearly-labeled, manually-verified constants in
`src/config/demo.js` instead of being fabricated:

- which branch/sandbox path IBM Bob's repair lives in (Bob created that
  worktree directly with `git worktree`, not through the backend's
  `SandboxManager`, so `GET /sandbox/{id}` has no record of it), and
- the repair sandbox's "after" test count (`11 passed / 0 failed`) — the
  backend's `POST /tests/run` always runs against its own configured target
  repository, so it has no endpoint to execute tests against an arbitrary
  external path on demand.

Both are called out explicitly in the UI (e.g. the Verification panel's
footnote) rather than presented as live data.

## Demo workflow

Clicking **RUN RECOVERY ANALYSIS**:

1. Checks the backend is reachable (`GET /health`) and updates the
   connection indicator.
2. Loads repository status (`GET /repository/status`).
3. Runs the target application's test suite (`POST /tests/run`) and renders
   the failing tests.
4. Loads the root-cause commit's metadata and diff.
5. Loads the repair commit's metadata and diff.
6. Renders the before/after verification comparison.

Each step's failure is caught independently and shown as an inline error
banner rather than crashing the whole page.

## Error handling

- **Backend unreachable**: the header shows "○ Backend Offline" and running
  the analysis shows a banner explaining how to start the backend.
- **Invalid/unknown Git reference**: the relevant panel shows the backend's
  error detail instead of a raw stack trace.
- **Test runner or sandbox errors**: surfaced the same way, scoped to the
  panel that failed — the rest of the dashboard still renders.

## Running the application

### Backend

```bash
cd codebase-icu
uvicorn backend.main:app --reload
```

Runs on `http://127.0.0.1:8000` by default. It now includes CORS middleware
(added specifically to support this dashboard) allowing
`http://localhost:5173` / `http://127.0.0.1:5173` by default; override with
the `CODEBASE_ICU_CORS_ORIGINS` environment variable (comma-separated) if
the frontend runs elsewhere.

### Frontend

```bash
cd codebase-icu/frontend
npm install
npm run dev
```

Runs on `http://localhost:5173` by default.

## Responsive design

Designed for desktop (1280×720 and up); panels reflow into a single column
and the pipeline nav becomes horizontally scrollable below ~720px so the
dashboard stays usable on a smaller laptop screen. Mobile is not a target.

## Testing

```bash
npm run test    # vitest — unit tests for the pure diff/test-result parsers
npm run build   # must succeed; also the most useful smoke test for JSX/import errors
```
