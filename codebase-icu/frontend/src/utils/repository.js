// Client-side half of repository selection. The backend is the authority
// on whether a path is usable (exists, is a directory, is a Git repository);
// this only rejects an empty field and turns the outcome into state the
// dashboard can render without throwing.

export const EMPTY_PATH_ERROR = 'Enter the path to a local Git repository.'

export async function selectRepository(apiClient, rawPath) {
  const path = (rawPath ?? '').trim()
  if (!path) return { ok: false, error: EMPTY_PATH_ERROR }

  try {
    const selection = await apiClient.configureRepository(path)
    return { ok: true, selection }
  } catch (err) {
    return {
      ok: false,
      error: err && err.message ? err.message : 'Repository configuration failed.',
    }
  }
}

export function isSameRepository(a, b) {
  return Boolean(a && b && a.path === b.path)
}
