// Extracts an "actual vs expected" status-code mismatch from a pytest
// assertion message, e.g. "assert 500 == 401" -> { actual: 500, expected: 401 }.
// Returns null when the reason doesn't match that shape, so callers can fall
// back to showing the raw failure reason instead.
export function parseStatusMismatch(reason) {
  if (!reason) return null
  const match = reason.match(/assert\s+(\d+)\s*==\s*(\d+)/)
  if (!match) return null
  return { actual: Number(match[1]), expected: Number(match[2]) }
}
