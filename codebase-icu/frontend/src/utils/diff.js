// Parses a unified `git diff`/`git show` text blob into renderable lines and
// summary stats. No git logic lives here - the diff text itself always comes
// from the backend's /repository/diff endpoint.

export function parseDiffLines(diffText) {
  if (!diffText) return []
  const lines = []
  for (const raw of diffText.split('\n')) {
    if (!raw) continue
    if (
      raw.startsWith('diff --git') ||
      raw.startsWith('index ') ||
      raw.startsWith('+++') ||
      raw.startsWith('---')
    ) {
      continue
    }
    if (raw.startsWith('@@')) {
      lines.push({ type: 'hunk', text: raw })
    } else if (raw.startsWith('+')) {
      lines.push({ type: 'add', text: raw.slice(1) })
    } else if (raw.startsWith('-')) {
      lines.push({ type: 'remove', text: raw.slice(1) })
    } else {
      lines.push({ type: 'context', text: raw.startsWith(' ') ? raw.slice(1) : raw })
    }
  }
  return lines
}

export function parseDiffStats(diffText) {
  if (!diffText) return { filesChanged: 0, linesAdded: 0, linesRemoved: 0 }
  let filesChanged = 0
  let linesAdded = 0
  let linesRemoved = 0
  for (const raw of diffText.split('\n')) {
    if (raw.startsWith('diff --git')) {
      filesChanged += 1
    } else if (raw.startsWith('+++') || raw.startsWith('---')) {
      continue
    } else if (raw.startsWith('+')) {
      linesAdded += 1
    } else if (raw.startsWith('-')) {
      linesRemoved += 1
    }
  }
  return { filesChanged, linesAdded, linesRemoved }
}
