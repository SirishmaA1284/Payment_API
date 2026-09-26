import { parseDiffLines } from '../utils/diff.js'

const MARKER = { add: '+', remove: '-', hunk: '@', context: ' ' }

export default function DiffView({ diffText, filePath, functionLabel }) {
  const lines = parseDiffLines(diffText)

  return (
    <div className="diff-view">
      {(filePath || functionLabel) && (
        <div className="diff-view__meta mono">
          {filePath && <span className="diff-view__file">{filePath}</span>}
          {functionLabel && <span className="diff-view__function">{functionLabel}</span>}
        </div>
      )}
      <pre className="diff-view__body">
        {lines.length === 0 && (
          <div className="diff-view__line diff-view__line--context">no diff available</div>
        )}
        {lines.map((line, index) => (
          <div key={index} className={`diff-view__line diff-view__line--${line.type}`}>
            <span className="diff-view__marker">{MARKER[line.type]}</span>
            <span className="diff-view__text">{line.text}</span>
          </div>
        ))}
      </pre>
    </div>
  )
}
