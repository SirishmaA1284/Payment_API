import Panel from './Panel.jsx'
import ErrorBanner from './ErrorBanner.jsx'
import { DEMO_CONFIG } from '../config/demo.js'

export default function VerificationPanel({ before, after, loading, error }) {
  const rows = [
    {
      label: 'Tests',
      before: before ? `${before.passed} / ${before.total}` : '—',
      after: after ? `${after.passed} / ${after.total}` : '—',
    },
    {
      label: 'Failures',
      before: before ? String(before.failed) : '—',
      after: after ? String(after.failed) : '—',
    },
    {
      label: 'Expired token',
      before: before && before.failed > 0 ? '500' : '—',
      after: after ? (after.failed === 0 ? '401' : 'still 500') : '—',
    },
    { label: 'Main branch', before: 'Broken', after: 'Unchanged' },
    { label: 'Sandbox', before: '—', after: after ? (after.failed === 0 ? 'Verified' : 'Still failing') : '—' },
  ]

  return (
    <Panel
      id="verification"
      eyebrow="STAGE 04 · CODEBASE ICU VERIFICATION"
      title="Recovery Verification"
      tone={after && after.failed === 0 ? 'success' : 'neutral'}
    >
      {error && <ErrorBanner message={error} />}

      {loading && !after && <p className="panel__hint">Running the sandbox&apos;s test suite…</p>}

      {!error && (
        <>
          <div className="verification-table-wrap">
            <table className="verification-table">
              <thead>
                <tr>
                  <th aria-hidden="true" />
                  <th>BEFORE</th>
                  <th>AFTER</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    <td className="mono">{row.before}</td>
                    <td className="mono">{row.after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="panel__hint">
            Both columns come from live <code className="mono">pytest</code> runs the backend
            executes on request: &ldquo;Before&rdquo; via <code className="mono">POST /tests/run</code>{' '}
            against <code className="mono">main</code>, &ldquo;After&rdquo; via{' '}
            <code className="mono">POST /sandbox/{DEMO_CONFIG.sandboxId}/tests</code> against the
            isolated repair sandbox. Neither figure is stored or hard-coded.
          </p>
        </>
      )}
    </Panel>
  )
}
