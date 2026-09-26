import Panel from './Panel.jsx'

const FLOW_STEPS = [
  'Failure detected',
  'Bob inspected tests',
  'Bob inspected source',
  'Bob inspected Git history',
  'Root cause identified',
]

export default function BobInvestigationPanel({ commit, failureCount, loading }) {
  return (
    <Panel eyebrow="IBM BOB INVESTIGATION" title="AI-Assisted Diagnosis" tone="info">
      <p className="panel__hint">
        IBM Bob 2.0 performed the diagnosis below by inspecting the failing tests, the
        application source, and the repository&apos;s Git history. The evidence shown here was
        supplied by the Codebase ICU backend; the backend itself performs no reasoning.
      </p>

      <ol className="bob-flow">
        {FLOW_STEPS.map((step) => (
          <li key={step} className="bob-flow__step">
            {step}
          </li>
        ))}
      </ol>

      <dl className="evidence-list">
        <div className="evidence-item">
          <dt>Test evidence</dt>
          <dd>
            {failureCount == null
              ? 'Run the recovery analysis to load live test evidence.'
              : `${failureCount} expired-token test${failureCount === 1 ? '' : 's'} return 500 instead of 401`}
          </dd>
        </div>
        <div className="evidence-item">
          <dt>Source evidence</dt>
          <dd className="mono">target-app/app/auth.py · get_current_user()</dd>
        </div>
        <div className="evidence-item">
          <dt>Git evidence</dt>
          <dd>
            {loading && 'Loading commit evidence…'}
            {!loading && commit && (
              <span className="mono">
                {commit.short_hash} introduced the problematic logging change
              </span>
            )}
            {!loading && !commit && 'Run the recovery analysis to load Git evidence.'}
          </dd>
        </div>
      </dl>
    </Panel>
  )
}
