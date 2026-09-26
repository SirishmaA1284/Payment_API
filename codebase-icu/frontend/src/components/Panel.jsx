export default function Panel({ id, eyebrow, title, tone = 'neutral', children }) {
  return (
    <section id={id} className={`panel panel--${tone}`}>
      {eyebrow && <div className="panel__eyebrow">{eyebrow}</div>}
      {title && <h2 className="panel__title">{title}</h2>}
      <div className="panel__body">{children}</div>
    </section>
  )
}
