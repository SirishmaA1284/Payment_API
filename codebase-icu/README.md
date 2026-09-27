# Codebase ICU — Infrastructure & Dashboard

**Codebase ICU — Explainable Autonomous Software Recovery** is a project
that investigates and repairs regressions in a target application, and
explains *why* the repair is correct rather than acting as a black box.

> **IBM Bob 2.0 is the core AI reasoning component of Codebase ICU.** The
> infrastructure in this module provides deterministic repository analysis,
> test execution, and isolated repair environments around that AI workflow.
> The dashboard visualizes the results of that workflow. Neither this
> backend nor the dashboard performs AI reasoning, root-cause analysis, or
> automated repair themselves.

## Scope

This directory (`codebase-icu/`) contains two pieces:

- **`backend/`** (Block 3) — the **deterministic infrastructure** the rest
  of the system is built on: reading Git history/diffs of the target
  repository, running the target application's test suite and parsing the
  results, and creating/tearing down isolated sandbox copies of the
  repository for a repair attempt to be tried in.
- **`frontend/`** (Block 5) — the **dashboard**, a React/Vite single-page
  app that turns the backend's evidence (plus IBM Bob's investigation and
  repair, sourced from the shared Git history) into the visible workflow
  Failure → Evidence → Root Cause → Safe Repair → Verified Recovery.

It intentionally does **not** contain: an LLM integration, autonomous
reasoning, or repair automation. IBM Bob remains responsible for actually
diagnosing root causes and proposing repairs; this module only gives it (and
the dashboard) safe, structured tools to do so with, and a way to show that
work to a viewer.

## Architecture

```text
Failure
   |
   v
Test Runner        <-- codebase-icu/backend/services/test_runner.py
   |
   v
Failure Information
   |
   v
Git Analyzer        <-- codebase-icu/backend/services/git_analyzer.py
   |
   v
Relevant Commits / Diffs
   |
   v
IBM Bob Investigation      (outside this module)
   |
   v
Repair Proposal            (outside this module)
   |
   v
Safe Sandbox        <-- codebase-icu/backend/services/sandbox_manager.py
   |
   v
Verification         (re-run Test Runner inside the sandbox)
   |
   v
Dashboard            <-- codebase-icu/frontend (this workflow, made visible)
```

All three backend services are exposed over a small FastAPI backend
(`codebase-icu/backend/main.py`) so other components (Bob, the dashboard)
can call them over HTTP instead of importing Python directly. The dashboard
is a plain HTTP client of that API — it contains no Git, test-running, or
sandbox logic of its own.

## Project structure

```text
codebase-icu/
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + routes
│   ├── models.py                # Pydantic request/response schemas
│   └── services/
│       ├── __init__.py
│       ├── git_analyzer.py      # safe subprocess wrapper around git
│       ├── test_runner.py       # runs & parses pytest output
│       ├── sandbox_manager.py   # isolated git worktrees
│       └── repository_selection.py  # runtime choice of the analyzed repository
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # temp-repo / temp-project fixtures
│   ├── test_git_analyzer.py
│   ├── test_test_runner.py
│   ├── test_sandbox_manager.py
│   ├── test_main_api.py
│   └── test_repository_selection.py
├── frontend/                    # dashboard - see frontend/README.md
│   ├── src/
│   │   ├── components/          # one component per dashboard panel/stage
│   │   ├── services/api.js      # fetch wrapper around this backend
│   │   ├── config/demo.js       # clearly-labeled, non-live demo constants
│   │   ├── utils/                # pure helpers + vitest unit tests
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── requirements.txt
└── README.md
```

## Setup

```bash
cd codebase-icu
python -m venv .venv
source .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The same virtual environment is used both to run the FastAPI backend and to
invoke `pytest` against the target application (via `sys.executable -m
pytest`), so it needs the target app's runtime dependencies too. In this
repo those happen to be a subset of `codebase-icu/requirements.txt`
(fastapi, pydantic, httpx, pytest), so no extra installs are required.

## Analyzing your own repository

Codebase ICU can analyze **any local Git repository you supply at runtime**,
not only the Payment API demo.

1. Start the stack (see [Running the full stack](#running-the-full-stack-backend--dashboard)).
2. In the dashboard, enter the repository's full local path in the
   **Repository** field at the top, e.g. `D:\CodebaseICU-Validation\repo-1`.
   The field is prefilled with the repository currently selected (the
   Payment API demo until you change it).
3. Click **RUN RECOVERY ANALYSIS** (or press Enter in the field). The
   dashboard first sends the path to `POST /repository/configure`; only if
   the backend accepts it does the analysis run, against that repository.
   If the path is rejected, the reason is shown under the field and nothing
   else runs.

Requirements for the repository:

- It must be a **local Git repository** (or a directory inside one — tests
  then run from that directory, like the demo's `target-app/`).
- For full recovery verification it needs a **runnable pytest suite** whose
  dependencies are installed in the backend's virtual environment (see
  [Setup](#setup)). If no tests are found or they cannot run, `POST
  /tests/run` returns a structured `error_code`/`error` instead of guessing.

Repairs are only ever tried in **isolated worktrees**: a sandbox is created
outside the selected repository, on its own `codebase-icu/sandbox-<id>`
branch, and is **never merged automatically** into the source repository's
branches — merging a repair is always your decision.

IBM Bob's recorded investigation and repair evidence (root-cause commit,
repair commit, repair sandbox — see `frontend/src/config/demo.js`) belong
to the Payment API demo. For any other repository the dashboard shows live
test results and states that no Bob investigation is recorded, rather than
showing the demo's evidence.

The selection is held in backend memory: restarting the backend returns to
the default repository.

## Configuration

The backend starts out inspecting one configurable **default target
repository path** (used until a repository is selected at runtime, as
described above):

| Variable                    | Default                                  | Meaning                                   |
|------------------------------|-------------------------------------------|--------------------------------------------|
| `CODEBASE_ICU_TARGET_REPO`  | `<this file>/../../target-app` (i.e. the sibling `target-app/` directory) | Directory the Git Analyzer and Test Runner operate on. |

The Sandbox Manager needs the **top-level** Git repository, not a
subdirectory of one (a `git worktree` cannot be created from a directory
that has no `.git` of its own). Since `target-app` is a subdirectory of the
Payment API repository rather than its own repository, the backend
discovers the real repository root generically at request time via
`GitAnalyzer.get_repo_root()` (`git rev-parse --show-toplevel`) — it does
not hard-code a path.

Sandboxes are created under `<repo-root's parent>/.codebase-icu-sandboxes/`
— a directory that sits *outside* the source repository's own working tree,
so sandbox activity never shows up as changes in the main repo's `git
status`.

To point the backend at a different repository without using the
dashboard, either call `POST /repository/configure` with `{"path": "..."}`,
or set `CODEBASE_ICU_TARGET_REPO` to that repository's path (or a
subdirectory of it) before starting uvicorn to change the default.

The backend also allows one cross-origin config for the dashboard:

| Variable                     | Default                                              | Meaning                                   |
|-------------------------------|-------------------------------------------------------|--------------------------------------------|
| `CODEBASE_ICU_CORS_ORIGINS`  | `http://localhost:5173,http://127.0.0.1:5173`         | Comma-separated origins allowed to call this API from a browser (the Vite dev server's default origin). |

## Running the backend

```bash
cd codebase-icu
uvicorn backend.main:app --reload
```

Interactive docs: `http://127.0.0.1:8000/docs`.

## Running the full stack (backend + dashboard)

### One-click launcher (Windows)

Double-click `start-codebase-icu.bat` at the repository root. It starts both
the backend and the frontend, each in its own terminal window, then opens a
short summary of the URLs. Once both windows show they're up, open
`http://localhost:5173`. The launcher does not modify any source code — it
only runs the same commands documented below in two separate windows.

### Manual startup

```bash
# terminal 1
cd codebase-icu
uvicorn backend.main:app --reload          # http://127.0.0.1:8000

# terminal 2
cd codebase-icu/frontend
npm install
npm run dev                                 # http://localhost:5173
```

Open `http://localhost:5173` and click **RUN RECOVERY ANALYSIS**. See
[`frontend/README.md`](frontend/README.md) for the dashboard's architecture,
configuration, and demo workflow in detail.

## API endpoints

| Method | Path                                   | Description                                              |
|--------|-----------------------------------------|------------------------------------------------------------|
| GET    | `/health`                               | Liveness check                                             |
| GET    | `/repository`                           | The repository currently analyzed: `path`, `repo_root`, `branch`, `is_default` |
| POST   | `/repository/configure`                 | Select the repository to analyze - body `{"path": "<absolute local path>"}`; same response shape as `GET /repository` |
| GET    | `/repository/status`                    | Current branch, clean/dirty state, changed files           |
| GET    | `/repository/commits?limit=&branch=`    | Recent commit summaries, newest first                      |
| GET    | `/repository/commits/{commit_hash}`     | Commit metadata, parent(s), changed files, stat summary     |
| GET    | `/repository/diff/{commit_hash}`        | Unified diff introduced by one commit                       |
| GET    | `/repository/file-history?path=&limit=` | Commits (newest first) that modified a given file           |
| POST   | `/tests/run`                            | Run `pytest -q` (optionally with extra args) in the target app and return structured results |
| POST   | `/sandbox/create`                       | Create an isolated Git worktree based on a ref (default `HEAD`) |
| GET    | `/sandbox/{sandbox_id}`                 | Sandbox path, branch, source commit, status                 |
| DELETE | `/sandbox/{sandbox_id}`                 | Remove a sandbox's worktree and throwaway branch             |
| POST   | `/sandbox/{sandbox_id}/tests`           | Run the test suite inside a sandbox's own working directory |

Every endpoint except `/health` and `/repository/configure` operates on the
**currently selected** repository, read per request.

File paths (`file-history`'s `path`, and the `changed_files` in status/commit
responses) are relative to the selected repository path, e.g. for the demo
`app/auth.py`, not `target-app/app/auth.py`.

### Error handling

- `POST /repository/configure` with a path that is empty, relative, missing,
  not a directory, or not inside a Git work tree → `400` with the reason; the
  previously selected repository stays selected
- Default repository path missing/invalid → `404`
- Invalid or unknown commit/branch reference → `400` (malformed reference) or `404` (well-formed but unknown)
- A failing Git subprocess call → `500` with the command's stderr (no secrets or environment variables are ever included)
- Unknown sandbox id → `404`
- Sandbox creation/cleanup failure → `500` with a safe diagnostic message

A **failing test in the target application is not a backend error** — `POST
/tests/run` always returns `200` with the full pass/fail breakdown; the
caller (Bob, later) decides what a failure means.

## How the Git Analyzer works

`backend/services/git_analyzer.py` wraps the `git` CLI via `subprocess.run`
with an explicit argv list — never `shell=True`, so there is no shell
interpolation to exploit. Before any value derived from a request reaches
`git`, it is validated:

- **References** (branch/tag/commit) must match a conservative allow-list of
  characters and must not start with `-` (which would otherwise be
  interpretable as a CLI flag instead of a ref).
- **File paths** are resolved against the repository root and rejected if
  they resolve outside of it (blocking `../../etc/passwd`-style traversal).

It exposes: `get_status()`, `get_commits()`, `get_commit_detail()`,
`get_commit_diff()`, `get_file_history()`, and `get_repo_root()`. All
non-zero exit codes are captured (including stderr) and raised as
`GitCommandError`; unknown/invalid references raise the more specific
`InvalidReferenceError`. The analyzer is generic — it is not aware of the
Payment API's regression or any specific commit hash, and it is exercised
in tests against both a disposable temporary repository and (structurally,
without asserting anything commit-specific) the real target-app repository.

## How the Test Runner works

`backend/services/test_runner.py` runs `<python> -m pytest -q` (plus any
extra args the caller supplies) as a subprocess inside the target project
directory, with a timeout. It then parses the captured stdout with a small
set of regular expressions that match pytest's own summary vocabulary
(`N passed`, `N failed`, `N skipped`, `N error(s)`) and its
`FAILED <nodeid> - <reason>` / `ERROR <nodeid> - <reason>` lines — nothing
is hard-coded to the Payment API's specific test names or counts. If the
summary line can't be parsed for any reason, `parsed_successfully` is
`False` but the raw `stdout`/`stderr` are still returned so a caller (or a
human) can inspect what happened.

When a run produces no usable result, the response also carries
`error_code` and a readable `error` (both `null` otherwise):

| `error_code`             | Meaning                                                    |
|---------------------------|-------------------------------------------------------------|
| `no_tests`                | pytest collected no tests (the repository has no suite)     |
| `collection_interrupted`  | collection failed, e.g. a test module's import error        |
| `tests_could_not_run`     | pytest failed to start or exited without a summary          |
| `timeout`                 | the suite exceeded the runner's timeout                     |

Tests always run in the selected repository's directory (for `/tests/run`)
or the same relative directory inside the sandbox (for
`/sandbox/{sandbox_id}/tests`) — never in the other one.

## How the Sandbox works

`backend/services/sandbox_manager.py` creates a `git worktree` — a second,
fully independent working copy checked out from a given ref onto its own
throwaway branch (`codebase-icu/sandbox-<id>`) — rooted under a dedicated
`.codebase-icu-sandboxes/` directory *outside* the source repository. This
gives a future repair attempt (Bob's proposed patch, applied and tested) a
disposable place to run without ever touching the source repository's
checked-out branch, staged changes, or HEAD.

Cleanup removes the worktree (`git worktree remove --force`, falling back to
a guarded filesystem delete if the worktree metadata is already gone) and
deletes the throwaway branch. Nothing in this module merges, rebases, or
pushes a sandbox's changes anywhere — that remains a decision for a later,
explicit step in the product, not something this infrastructure does on its
own.

Each selected repository gets its own sandbox manager, keyed by repository
root: sandboxes are looked up only among that repository's worktrees, and
switching back to a repository restores access to (and cleanup of) the
sandboxes created there. If a repository sits at a filesystem root (so has
no parent directory to hold `.codebase-icu-sandboxes/`), sandboxes go under
the system temp directory instead; a sandbox root inside the source
repository is refused.

## Security / safety considerations

- No `shell=True` anywhere; all subprocess calls use argv lists.
- The repository path submitted to `/repository/configure` is treated only
  as a filesystem path: it must be absolute, exist, be a directory, and be
  inside a Git work tree whose root `git rev-parse --show-toplevel` resolves.
  The API accepts no Git commands or arguments from the client, and its
  responses return only the path, repository root and branch — never file
  contents, `.env` values, or environment variables.
- Running a repository's tests executes that repository's code (its test
  modules, `conftest.py`, etc.) with the backend's privileges. Only select
  repositories you trust.
- Git references and file paths are validated before being passed to `git`.
- The sandbox manager refuses to delete the source repository or anything
  outside its own sandbox root, even if asked to (`_assert_safe_to_delete`).
- Sandbox ids and branch names are generated server-side (`uuid4`), never
  taken from caller input, so a caller cannot direct cleanup at an arbitrary
  path by choosing a crafted id.
- API error responses return command output/stderr for diagnosis but never
  environment variables or other process secrets.
- The Test Runner enforces a timeout so a hung test suite can't hang the API
  indefinitely.

## Running the infrastructure tests

```bash
cd codebase-icu
pytest -q
```

Tests for the Git Analyzer and Test Runner primarily use disposable,
throwaway Git repositories / pytest projects created under pytest's
`tmp_path`, plus a small number of structural (non-regression-specific)
checks against the real `target-app` repository. Sandbox Manager tests run
exclusively against a temporary repository — they never create a worktree
against the real Payment API repository, so running this suite cannot
disturb the target application or its Git history.

## Running the dashboard's checks

```bash
cd codebase-icu/frontend
npm run test    # vitest unit tests: diff/test-result parsers, repository selection, API client
npm run build   # production build - also the main JSX/import smoke test
```

## Known limitations

- The runtime repository selection is held in memory and is global to the
  backend process (one selection shared by every dashboard tab); restarting
  the backend returns to the default repository.
- Tests run with the backend's own Python interpreter, so a selected
  repository's test dependencies must be installed in `codebase-icu/.venv`;
  otherwise `/tests/run` reports `collection_interrupted` /
  `tests_could_not_run`. Only pytest suites are supported.

- Sandbox bookkeeping (`SandboxManager._sandboxes`) is in-memory only and
  scoped to one `SandboxManager` instance/process; restarting the backend
  process forgets sandboxes it previously created (their worktrees remain on
  disk and can still be cleaned up manually with `git worktree list` /
  `git worktree remove` against the repository root if needed).
- The pytest-output parser matches common, stable pytest summary phrasing;
  a heavily customized pytest plugin that changes that phrasing could reduce
  `parsed_successfully` to `False` (raw output is preserved in that case).
