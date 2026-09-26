import Panel from './Panel.jsx'
import ErrorBanner from './ErrorBanner.jsx'
import { parseStatusMismatch } from '../utils/testResult.js'

export default function FailurePanel({ result, loading, error }) {
  if (error) {
    return (
      <Panel id="failure" eyebrow="STAGE 01" title="Failure" tone="danger">
        <ErrorBanner message={error} />
      </Panel>
    )
  }

  if (!result) {
    return (
      <Panel id="failure" eyebrow="STAGE 01" title="Failure" tone="neutral">
        <p className="panel__hint">
          {loading
            ? 'Running the target application test suite…'
            : 'Run the recovery analysis to pull live test results from the target application.'}
        </p>
      </Panel>
    )
  }

  const hasFailures = result.failed > 0

  return (
    <Panel id="failure" eyebrow="STAGE 01" title="Failure" tone={hasFailures ? 'danger' : 'success'}>
      <div className="failure-summary">
        <span className="failure-summary__icon" aria-hidden="true">
          {hasFailures ? '⚠' : '✓'}
        </span>
        <span className="failure-summary__text">
          {hasFailures
            ? `${result.failed} FAILURE${result.failed === 1 ? '' : 'S'} DETECTED`
            : 'ALL TESTS PASSING'}
        </span>
      </div>

      {hasFailures && (
        <ul className="failing-test-list">
          {result.failing_tests.map((test) => {
            const mismatch = parseStatusMismatch(test.reason)
            return (
              <li key={test.node_id} className="failing-test">
                <div className="failing-test__id mono">{test.node_id}</div>
                <div className="failing-test__detail">
                  {mismatch
                    ? `Expected ${mismatch.expected} · Received ${mismatch.actual}`
                    : test.reason || 'No failure detail captured'}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <div className="failure-summary__totals mono">
        {result.passed} / {result.total} tests passing
      </div>
    </Panel>
  )
}
