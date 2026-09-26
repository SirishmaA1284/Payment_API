import { useCallback, useEffect, useState } from 'react'
import Header from './components/Header.jsx'
import PipelineNav from './components/PipelineNav.jsx'
import RunAnalysisButton from './components/RunAnalysisButton.jsx'
import FailurePanel from './components/FailurePanel.jsx'
import BobInvestigationPanel from './components/BobInvestigationPanel.jsx'
import RootCausePanel from './components/RootCausePanel.jsx'
import RepairPanel from './components/RepairPanel.jsx'
import VerificationPanel from './components/VerificationPanel.jsx'
import ErrorBanner from './components/ErrorBanner.jsx'
import { api } from './services/api.js'
import { DEMO_CONFIG } from './config/demo.js'

function describeError(err) {
  return err && err.message ? err.message : 'Unexpected error'
}

export default function App() {
  const [backendConnected, setBackendConnected] = useState(null)
  const [checkingBackend, setCheckingBackend] = useState(true)
  const [repoStatus, setRepoStatus] = useState(null)

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
    checkBackend()
  }, [checkBackend])

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

    try {
      setRepoStatus(await api.repositoryStatus())
    } catch {
      setRepoStatus(null) // non-fatal, the rest of the run can continue
    }

    setProgressLabel('Running target application tests on main…')
    try {
      setTestResult(await api.runTests())
    } catch (err) {
      setTestError(describeError(err))
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
  }, [checkBackend])

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
        <RunAnalysisButton onRun={runRecoveryAnalysis} running={running} progressLabel={progressLabel} />

        <ErrorBanner message={globalError} />

        <FailurePanel result={testResult} loading={running && !testResult} error={testError} />

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
      </main>

      <footer className="app-footer">
        IBM Bob 2.0 is the AI reasoning component of Codebase ICU. This dashboard visualizes
        deterministic evidence produced by the Codebase ICU backend and Bob&apos;s
        investigation — it performs no reasoning of its own.
      </footer>
    </div>
  )
}
