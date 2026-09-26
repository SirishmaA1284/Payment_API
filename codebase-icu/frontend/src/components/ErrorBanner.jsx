export default function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div className="error-banner" role="alert">
      <span className="error-banner__icon" aria-hidden="true">
        ✕
      </span>
      <span>{message}</span>
    </div>
  )
}
