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
3. **Safe Repair** — the isolated repair diff, plus the sandbox's own live
   test results (via `GET /sandbox/{sandbox_id}` and
   `POST /sandbox/{sandbox_id}/tests`), in a clear MAIN vs. SANDBOX comparison
   making it visible that `main` was never touched.
4. **Verification** — a before/after comparison table built from the two
   live test runs (`main` via `POST /tests/run`, the sandbox via
   `POST /sandbox/{sandbox_id}/tests`), labeled as "CODEBASE ICU
   VERIFICATION" to distinguish it from Bob's own diagnosis.

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
│   │                     backend logic is duplicated here (+ api.test.js)
│   ├── config/
│   │   └── demo.js       clearly-labeled demo identifiers/configuration
│   │                     used by the dashboard (see below)
│   ├── utils/            pure helpers (diff parsing, failure-reason
│   │                     parsing, repository selection) with small
│   │                     vitest unit tests
│   ├── App.jsx           orchestrates the "Run Recovery Analysis" flow
│   ├── main.jsx          React entry point
│   └── styles.css        the entire visual design (plain CSS, no framework)
├── public/
│   └── favicon.svg
├── index.html
├── package.json
└── vite.config.js
```

### Live data vs. configuration

Everything the dashboard displays is fetched live from the backend at
analysis time:

- **Repository status** — `GET /repository/status`.
- **Target application test results** — `POST /tests/run`.
- **Root-cause commit metadata/diff** — `GET /repository/commits/{hash}` and
  `GET /repository/diff/{hash}` (Git worktrees share one object database, so
  this works even though the commit was made on a different branch/worktree
  than the one the backend has checked out).
- **Repair commit metadata/diff** — the same two endpoints, for the repair
  commit.
- **Sandbox information** — `GET /sandbox/{sandbox_id}`.
- **Repair sandbox test results** — `POST /sandbox/{sandbox_id}/tests`, which
  runs the target application's `pytest` suite inside that sandbox's own
  working directory and returns the actual, current pass/fail counts. This
  is not a stored or hard-coded value.

`src/config/demo.js` holds only **identifiers**, not results: which
root-cause commit, which repair commit, and which sandbox this demonstration
points the dashboard at. The dashboard needs these to know *what* to ask the
backend about, since the backend has no "list everything relevant" endpoint.
The repair sandbox itself is a Git worktree IBM Bob created directly with
`git worktree`, checked out on its own branch and deliberately isolated from
`main` — `main` is never modified by, or merged with, that repair.

## Choosing the repository to analyze

The **Repository** field at the top of the dashboard holds the local Git
repository to analyze, e.g. `D:\CodebaseICU-Validation\repo-1`. On load it
is prefilled from `GET /repository` with the backend's current selection,
which is the Payment API demo until you change it. The line under the field
shows the repository the backend has actually selected and its branch.

The repository must be a local Git repository with a runnable pytest suite
for full recovery verification. The backend validates the path; the
dashboard only rejects an empty field (`src/utils/repository.js`). Repairs
are only tried in isolated worktrees and are never merged into the source
repository automatically — see the backend
[README](../README.md#analyzing-your-own-repository).

IBM Bob's investigation/repair evidence (`src/config/demo.js`) belongs to
the Payment API demo, so it is shown only while the demo repository is
selected (`is_default` in the backend's response). For any other repository
the dashboard shows that repository's live test results and a notice that no
Bob investigation is recorded for it.

## Demo workflow

Clicking **RUN RECOVERY ANALYSIS** (or pressing Enter in the Repository
field):

1. Checks the backend is reachable (`GET /health`) and updates the
   connection indicator.
2. Sends the entered path to `POST /repository/configure`. If the backend
   rejects it, the reason is shown under the field and the analysis stops
   here; nothing else runs. Selecting a different repository clears the
   previous repository's results.
3. Loads repository status (`GET /repository/status`), then runs the
   selected repository's test suite (`POST /tests/run`) and renders the
   failing tests, or the backend's structured error if the suite could not
   run. For a repository other than the demo, the analysis ends here.
4. Loads the root-cause commit's metadata and diff.
5. Loads the repair commit's metadata and diff.
6. Loads the repair sandbox's information (`GET /sandbox/{sandbox_id}`).
7. Runs the test suite inside that sandbox
   (`POST /sandbox/{sandbox_id}/tests`).
8. Renders the before/after verification comparison from the two live test
   runs (steps 3 and 7).

Each step's failure is caught independently and shown as an inline error
banner rather than crashing the whole page.

## Error handling

- **Invalid repository path** (missing, not a directory, not a Git
  repository, relative): the backend's reason is shown under the Repository
  field, the analysis does not start, and the previous selection stays.
- **Tests cannot run** (no tests, collection errors, timeout): the Failure
  panel shows the backend's `error` instead of a pass/fail count.
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
npm run test    # vitest — diff/test-result parsers, repository selection, API client
npm run build   # must succeed; also the most useful smoke test for JSX/import errors
```
