export default function ConnectionStatus({ connected, checking }) {
  let label = 'Backend Offline'
  let stateClass = 'is-offline'
  if (checking && connected === null) {
    label = 'Checking backend…'
    stateClass = 'is-checking'
  } else if (connected) {
    label = 'Backend Connected'
    stateClass = 'is-online'
  }

  return (
    <div className={`connection-status ${stateClass}`}>
      <span className="connection-status__dot" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
