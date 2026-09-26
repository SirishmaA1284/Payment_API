// Thin fetch wrapper around the Codebase ICU FastAPI backend
// (codebase-icu/backend/main.py). No backend logic is duplicated here -
// this module only shapes HTTP calls and surfaces readable errors.

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE_URL

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new ApiError(
      `Cannot reach the Codebase ICU backend at ${BASE_URL}. Is it running?`,
      0,
    )
  }

  const text = await response.text()
  let body = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!response.ok) {
    const detail = (body && body.detail) || response.statusText || 'Request failed'
    throw new ApiError(detail, response.status)
  }

  return body
}

function withQuery(path, params) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) search.set(key, String(value))
  })
  const qs = search.toString()
  return qs ? `${path}?${qs}` : path
}

export const api = {
  health: () => request('/health'),

  repositoryStatus: () => request('/repository/status'),

  repositoryCommits: ({ limit = 20, branch } = {}) =>
    request(withQuery('/repository/commits', { limit, branch })),

  repositoryCommitDetail: (commitHash) =>
    request(`/repository/commits/${encodeURIComponent(commitHash)}`),

  repositoryDiff: (commitHash) =>
    request(`/repository/diff/${encodeURIComponent(commitHash)}`),

  repositoryFileHistory: ({ path, limit = 20 }) =>
    request(withQuery('/repository/file-history', { path, limit })),

  runTests: (extraArgs) =>
    request('/tests/run', {
      method: 'POST',
      body: JSON.stringify({ extra_args: extraArgs ?? null }),
    }),

  createSandbox: (sourceRef = 'HEAD') =>
    request('/sandbox/create', {
      method: 'POST',
      body: JSON.stringify({ source_ref: sourceRef }),
    }),

  getSandbox: (sandboxId) => request(`/sandbox/${encodeURIComponent(sandboxId)}`),

  deleteSandbox: (sandboxId) =>
    request(`/sandbox/${encodeURIComponent(sandboxId)}`, { method: 'DELETE' }),

  runSandboxTests: (sandboxId, extraArgs) =>
    request(`/sandbox/${encodeURIComponent(sandboxId)}/tests`, {
      method: 'POST',
      body: JSON.stringify({ extra_args: extraArgs ?? null }),
    }),
}
