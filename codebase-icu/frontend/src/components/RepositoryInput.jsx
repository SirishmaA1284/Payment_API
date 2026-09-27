import ErrorBanner from './ErrorBanner.jsx'

export default function RepositoryInput({ value, onChange, onSubmit, selected, error, disabled }) {
  return (
    <form
      className="repository-input"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <label className="repository-input__label" htmlFor="repository-path">
        Repository
      </label>
      <input
        id="repository-path"
        className="repository-input__field mono"
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="D:\path\to\local\git-repository"
        spellCheck={false}
        autoComplete="off"
        disabled={disabled}
      />
      <div className="repository-input__selected mono">
        {selected
          ? `Selected: ${selected.path} · branch ${selected.branch}${selected.is_default ? ' · demo' : ''}`
          : 'No repository selected yet.'}
      </div>
      <ErrorBanner message={error} />
    </form>
  )
}
