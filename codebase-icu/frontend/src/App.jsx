import { useCallback, useEffect, useState } from 'react'
import Header from './components/Header.jsx'
import PipelineNav from './components/PipelineNav.jsx'
import RunAnalysisButton from './components/RunAnalysisButton.jsx'
import RepositoryInput from './components/RepositoryInput.jsx'
import Panel from './components/Panel.jsx'
import FailurePanel from './components/FailurePanel.jsx'
import BobInvestigationPanel from './components/BobInvestigationPanel.jsx'
import RootCausePanel from './components/RootCausePanel.jsx'
import RepairPanel from './components/RepairPanel.jsx'
import VerificationPanel from './components/VerificationPanel.jsx'
import ErrorBanner from './components/ErrorBanner.jsx'
import { api } from './services/api.js'
import { DEMO_CONFIG } from './config/demo.js'
import { isSameRepository, selectRepository } from './utils/repository.js'

function describeError(err) {
  return err && err.message ? err.message : 'Unexpected error'
}

export default function App() {
  const [backendConnected, setBackendConnected] = useState(null)
  const [checkingBackend, setCheckingBackend] = useState(true)
  const [repoStatus, setRepoStatus] = useState(null)

  const [repoInput, setRepoInput] = useState('')
  const [selectedRepo, setSelectedRepo] = useState(null)
  const [repoError, setRepoError] = useState(null)

  const [running, setRunning] = useState(false)
  const [progressLabel, setProgressLabel] = useState('')
  const [globalError, setGlobalError] = useState(null)

  const [testResult, setTestResult] = useState(null)
  const [testError, setTestError] = useState(null)

  const [rootCauseCommit, setRootCauseCommit] = useState(null)
  const [rootCauseDiff, setRootCauseDiff] = useState(null)
  const [rootCauseError, setRootCauseError] = useState(null)

  const [repairCommit, setRepairCommit] = useState(null)
  const [repairDiff, setRepairDiff] = useState(null)
  const [repairError, setRepairError] = useState(null)

  const [sandboxInfo, setSandboxInfo] = useState(null)
  const [sandboxResult, setSandboxResult] = useState(null)
  const [sandboxError, setSandboxError] = useState(null)

  const checkBackend = useCallback(async () => {
    setCheckingBackend(true)
    try {
      await api.health()
      setBackendConnected(true)
      return true
    } catch {
      setBackendConnected(false)
      return false
    } finally {
      setCheckingBackend(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    checkBackend().then(async (online) => {
      if (!online) return
      try {
        const current = await api.currentRepository()
        if (cancelled) return
        setSelectedRepo(current)
        // Prefill with the backend's current (default: demo) repository,
        // unless the user already started typing.
        setRepoInput((typed) => typed || current.path)
      } catch {
        // Non-fatal: the path can still be entered and configured manually.
      }
    })
    return () => {
      cancelled = true
    }
  }, [checkBackend])

  const clearResults = useCallback(() => {
    setRepoStatus(null)
    setTestResult(null)
    setRootCauseCommit(null)
    setRootCauseDiff(null)
    setRepairCommit(null)
    setRepairDiff(null)
    setSandboxInfo(null)
    setSandboxResult(null)
  }, [])

  const runRecoveryAnalysis = useCallback(async () => {
    setRunning(true)
    setGlobalError(null)
    setTestError(null)
    setRootCauseError(null)
    setRepairError(null)
    setSandboxError(null)

    setProgressLabel('Checking repository status…')
    const online = await checkBackend()
    if (!online) {
      setGlobalError(
        'Cannot reach the Codebase ICU backend. Start it with "uvicorn backend.main:app --reload" from inside codebase-icu/.',
      )
      setRunning(false)
      setProgressLabel('')
      return
    }

    // Select the repository first; nothing else runs unless the backend
    // accepts it.
    setProgressLabel('Configuring repository…')
    const outcome = await selectRepository(api, repoInput)
    if (!outcome.ok) {
      setRepoError(outcome.error)
      setRunning(false)
      setProgressLabel('')
      return
    }
    setRepoError(null)
    const selection = outcome.selection
    if (!isSameRepository(selection, selectedRepo)) clearResults()
    setSelectedRepo(selection)

    setProgressLabel('Checking repository status…')
    try {
      setRepoStatus(await api.repositoryStatus())
    } catch {
      setRepoStatus(null) // non-fatal, the rest of the run can continue
    }

    setProgressLabel(`Running target application tests on ${selection.branch}…`)
    try {
      setTestResult(await api.runTests())
    } catch (err) {
      setTestError(describeError(err))
    }

    // IBM Bob's recorded investigation and repair (DEMO_CONFIG) belong to
    // the Payment API demo only; other repositories get live test results
    // but no Bob evidence is fabricated for them.
    if (!selection.is_default) {
      setProgressLabel('')
      setRunning(false)
      return
    }

    setProgressLabel('Loading root-cause commit evidence…')
    try {
      const [commit, diffResponse] = await Promise.all([
        api.repositoryCommitDetail(DEMO_CONFIG.rootCauseCommit),
        api.repositoryDiff(DEMO_CONFIG.rootCauseCommit),
      ])
      setRootCauseCommit(commit)
      setRootCauseDiff(diffResponse.diff)
    } catch (err) {
      setRootCauseError(describeError(err))
    }

    setProgressLabel('Loading isolated repair evidence…')
    try {
      const [commit, diffResponse] = await Promise.all([
        api.repositoryCommitDetail(DEMO_CONFIG.repairCommit),
        api.repositoryDiff(DEMO_CONFIG.repairCommit),
      ])
      setRepairCommit(commit)
      setRepairDiff(diffResponse.diff)
    } catch (err) {
      setRepairError(describeError(err))
    }

    setProgressLabel('Locating repair sandbox and running its tests…')
    try {
      const [info, result] = await Promise.all([
        api.getSandbox(DEMO_CONFIG.sandboxId),
        api.runSandboxTests(DEMO_CONFIG.sandboxId),
      ])
      setSandboxInfo(info)
      setSandboxResult(result)
    } catch (err) {
      setSandboxError(describeError(err))
    }

    setProgressLabel('')
    setRunning(false)
  }, [checkBackend, clearResults, repoInput, selectedRepo])

  const showDemoEvidence = !selectedRepo || selectedRepo.is_default

  const stageStatus = {
    failure: !testResult ? 'pending' : testResult.failed > 0 ? 'active' : 'done',
    investigation: rootCauseCommit ? 'done' : testResult ? 'active' : 'pending',
    repair: repairCommit ? 'done' : rootCauseCommit ? 'active' : 'pending',
    verification: sandboxResult ? 'done' : repairCommit ? 'active' : 'pending',
  }

  return (
    <div className="app-shell">
      <Header connected={backendConnected} checking={checkingBackend} repoBranch={repoStatus?.branch} />
      <PipelineNav statusById={stageStatus} />

      <main className="app-main">
        <RepositoryInput
          value={repoInput}
          onChange={setRepoInput}
          onSubmit={runRecoveryAnalysis}
          selected={selectedRepo}
          error={repoError}
          disabled={running}
        />

        <RunAnalysisButton onRun={runRecoveryAnalysis} running={running} progressLabel={progressLabel} />

        <ErrorBanner message={globalError} />

        <FailurePanel result={testResult} loading={running && !testResult} error={testError} />

        {showDemoEvidence ? (
          <>
            <BobInvestigationPanel
              commit={rootCauseCommit}
              failureCount={testResult ? testResult.failed : null}
              loading={running && !rootCauseCommit}
            />

            <RootCausePanel
              commit={rootCauseCommit}
              diff={rootCauseDiff}
              loading={running && !rootCauseCommit}
              error={rootCauseError}
            />

            <RepairPanel
              diff={repairDiff}
              commit={repairCommit}
              mainResult={testResult}
              sandboxInfo={sandboxInfo}
              sandboxResult={sandboxResult}
              loading={running && !repairCommit}
              error={repairError || sandboxError}
            />

            <VerificationPanel before={testResult} after={sandboxResult} loading={running && !sandboxResult} error={sandboxError} />
          </>
        ) : (
          <Panel eyebrow="IBM BOB INVESTIGATION" title="No Recorded Investigation" tone="neutral">
            <p className="panel__hint">
              The test results above are live for the selected repository. IBM Bob&apos;s
              investigation, repair, and sandbox verification shown in this dashboard are
              recorded for the Payment API demo only, so no root cause or repair is displayed
              for this repository.
            </p>
          </Panel>
        )}
      </main>

      <footer className="app-footer">
        IBM Bob 2.0 is the AI reasoning component of Codebase ICU. This dashboard visualizes
        deterministic evidence produced by the Codebase ICU backend and Bob&apos;s
        investigation — it performs no reasoning of its own.
      </footer>
    </div>
  )
}
