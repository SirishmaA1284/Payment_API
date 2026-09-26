import ConnectionStatus from './ConnectionStatus.jsx'

export default function Header({ connected, checking, repoBranch }) {
  return (
    <header className="app-header">
      <div>
        <div className="app-header__brand">CODEBASE ICU</div>
        <div className="app-header__subtitle">Explainable Autonomous Software Recovery</div>
      </div>
      <div className="app-header__meta">
        {repoBranch && <span className="app-header__branch mono">branch: {repoBranch}</span>}
        <ConnectionStatus connected={connected} checking={checking} />
      </div>
    </header>
  )
}
