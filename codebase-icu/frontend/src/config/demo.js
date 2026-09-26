// Identifiers this specific hackathon demo cares about, which the backend
// has no "list everything" endpoint to enumerate on its own - not fabricated
// results, just addresses:
//
//  - which commit introduced the bug and which commit repairs it (used to
//    fetch their real metadata/diff from the backend), and
//  - which sandbox holds IBM Bob's repair. That sandbox is a Git worktree
//    Bob created directly with `git worktree` (not through this backend's
//    POST /sandbox/create), so there is no "list sandboxes" call that would
//    surface it - the backend can still look it up and run tests inside it
//    by name via GET/POST /sandbox/{sandbox_id}[/tests], because
//    SandboxManager discovers any Git worktree by its directory name, not
//    only ones it created itself.
//
// Every number the dashboard displays - including the "after repair" test
// count - is fetched live from the backend (see services/api.js). Nothing
// here is a test result.
export const DEMO_CONFIG = {
  rootCauseCommit: '9af9184',
  repairCommit: 'fe69a0b',
  repairBranch: 'codebase-icu/repair-expired-token',
  sandboxId: 'repair-sandbox',
  affectedFile: 'target-app/app/auth.py',
  affectedFunction: 'get_current_user()',
}
