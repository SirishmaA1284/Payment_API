export default function RunAnalysisButton({ onRun, running, progressLabel }) {
  return (
    <div className="run-analysis">
      <button
        type="button"
        className="run-analysis__button"
        onClick={onRun}
        disabled={running}
      >
        {running ? 'RUNNING RECOVERY ANALYSIS…' : 'RUN RECOVERY ANALYSIS'}
      </button>
      <div className="run-analysis__progress" aria-live="polite">
        {running ? progressLabel : 'Pulls live evidence from the Codebase ICU backend.'}
      </div>
    </div>
  )
}
