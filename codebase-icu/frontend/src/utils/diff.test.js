import { describe, expect, it } from 'vitest'
import { parseDiffLines, parseDiffStats } from './diff.js'

const SAMPLE_DIFF = `diff --git a/target-app/app/auth.py b/target-app/app/auth.py
index 097bf7e..c072748 100644
--- a/target-app/app/auth.py
+++ b/target-app/app/auth.py
@@ -80,7 +80,7 @@ def get_current_user(authorization: str = Header(default=None)) -> str:
     try:
         return decode_token(token)
     except ExpiredTokenError as exc:
-        logger.info("Rejected expired token (age=%.0fs)", time.time() - issued_at)
+        logger.info("Rejected expired token")
         raise HTTPException(
`

describe('parseDiffStats', () => {
  it('counts files changed and added/removed lines, ignoring file headers', () => {
    expect(parseDiffStats(SAMPLE_DIFF)).toEqual({
      filesChanged: 1,
      linesAdded: 1,
      linesRemoved: 1,
    })
  })

  it('returns zeros for empty input', () => {
    expect(parseDiffStats('')).toEqual({ filesChanged: 0, linesAdded: 0, linesRemoved: 0 })
  })
})

describe('parseDiffLines', () => {
  it('classifies hunk, add, remove, and context lines and strips file headers', () => {
    const lines = parseDiffLines(SAMPLE_DIFF)
    expect(lines.some((l) => l.type === 'hunk')).toBe(true)
    expect(lines.filter((l) => l.type === 'add')).toHaveLength(1)
    expect(lines.filter((l) => l.type === 'remove')).toHaveLength(1)
    expect(lines.some((l) => l.text.includes('diff --git'))).toBe(false)

    const added = lines.find((l) => l.type === 'add')
    expect(added.text).toContain('Rejected expired token')
    expect(added.text).not.toContain('issued_at')
  })

  it('returns an empty array for empty input', () => {
    expect(parseDiffLines('')).toEqual([])
  })
})
