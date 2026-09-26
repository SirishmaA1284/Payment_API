import Panel from './Panel.jsx'
import DiffView from './DiffView.jsx'
import ErrorBanner from './ErrorBanner.jsx'
import { DEMO_CONFIG } from '../config/demo.js'
import { parseDiffStats } from '../utils/diff.js'

export default function RepairPanel({
  diff,
  commit,
  mainResult,
  sandboxInfo,
  sandboxResult,
  loading,
  error,
}) {
  const stats = parseDiffStats(diff)
  const sandboxVerified = sandboxResult && sandboxResult.failed === 0

  return (
    <Panel id="repair" eyebrow="STAGE 03" title="Safe Repair" tone="info">
      {error && <ErrorBanner message={error} />}

      {!error && (
        <>
          <div className="repair-meta">
            <div className="repair-meta__item">
              <div className="repair-meta__label">Branch</div>
              <div className="mono">{sandboxInfo?.branch || DEMO_CONFIG.repairBranch}</div>
            </div>
            <div className="repair-meta__item">
              <div className="repair-meta__label">Sandbox</div>
              <div className="mono">{DEMO_CONFIG.sandboxId}</div>
            </div>
            <div className="repair-meta__item">
              <div className="repair-meta__label">Files changed</div>
              <div className="mono">{diff ? stats.filesChanged : '—'}</div>
            </div>
            <div className="repair-meta__item">
              <div className="repair-meta__label">Lines changed</div>
              <div className="mono">{diff ? stats.linesAdded + stats.linesRemoved : '—'}</div>
            </div>
          </div>

          {loading && <p className="panel__hint">Loading repair diff…</p>}

          {!loading && diff && (
            <DiffView
              diffText={diff}
              filePath={DEMO_CONFIG.affectedFile}
              functionLabel={DEMO_CONFIG.affectedFunction}
            />
          )}

          {!loading && commit && (
            <div className="commit-callout">
              <div className="commit-callout__label">Repair commit</div>
              <div className="commit-callout__hash mono">{commit.short_hash}</div>
              <div className="commit-callout__message">&ldquo;{commit.message}&rdquo;</div>
            </div>
          )}

          <div className="isolation-compare">
            <div className="isolation-card isolation-card--broken">
              <div className="isolation-card__title">MAIN</div>
              <div className="isolation-card__metric mono">
                {mainResult ? `${mainResult.passed} / ${mainResult.total}` : '—'}
              </div>
              <div className="isolation-card__tag">INTENTIONALLY BROKEN</div>
            </div>
            <div className={`isolation-card ${sandboxVerified ? 'isolation-card--verified' : 'isolation-card--broken'}`}>
              <div className="isolation-card__title">REPAIR SANDBOX</div>
              <div className="isolation-card__metric mono">
                {sandboxResult ? `${sandboxResult.passed} / ${sandboxResult.total}` : '—'}
              </div>
              <div className="isolation-card__tag">
                {sandboxResult ? (sandboxVerified ? 'VERIFIED' : 'STILL FAILING') : 'NOT YET RUN'}
              </div>
            </div>
          </div>

          <p className="panel__hint">
            Sandbox test counts come from a live <code className="mono">pytest</code> run the
            backend executes inside the sandbox&apos;s own working directory
            (<code className="mono">POST /sandbox/{DEMO_CONFIG.sandboxId}/tests</code>) — not a
            stored or hard-coded value.
          </p>

          <div className="main-unchanged-banner">MAIN UNCHANGED</div>
        </>
      )}
    </Panel>
  )
}
