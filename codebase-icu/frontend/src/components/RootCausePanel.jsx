import Panel from './Panel.jsx'
import DiffView from './DiffView.jsx'
import ErrorBanner from './ErrorBanner.jsx'
import { DEMO_CONFIG } from '../config/demo.js'

export default function RootCausePanel({ commit, diff, loading, error }) {
  return (
    <Panel id="investigation" eyebrow="STAGE 02" title="Investigation · Root Cause" tone="info">
      {error && <ErrorBanner message={error} />}

      {!error && (
        <>
          <div className="badge badge--confirmed">ROOT CAUSE CONFIRMED</div>

          <div className="root-cause__location mono">
            {DEMO_CONFIG.affectedFile} → {DEMO_CONFIG.affectedFunction}
          </div>

          <p className="root-cause__explanation">
            <code className="mono">issued_at</code> is referenced inside the{' '}
            <code className="mono">ExpiredTokenError</code> exception handler, but it is a
            local variable belonging to a different function and is never in scope there.
            Handling an expired token therefore raises an unhandled{' '}
            <code className="mono">NameError</code>, which surfaces to the client as{' '}
            <strong>500 Internal Server Error</strong> instead of the intended{' '}
            <strong>401 Unauthorized</strong>.
          </p>

          {loading && <p className="panel__hint">Loading commit evidence…</p>}

          {!loading && commit && (
            <div className="commit-callout">
              <div className="commit-callout__label">Introduced by</div>
              <div className="commit-callout__hash mono">{commit.short_hash}</div>
              <div className="commit-callout__message">&ldquo;{commit.message}&rdquo;</div>
            </div>
          )}

          {!loading && diff && (
            <DiffView
              diffText={diff}
              filePath={DEMO_CONFIG.affectedFile}
              functionLabel={DEMO_CONFIG.affectedFunction}
            />
          )}
        </>
      )}
    </Panel>
  )
}
