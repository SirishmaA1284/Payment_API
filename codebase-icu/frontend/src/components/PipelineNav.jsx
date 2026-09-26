import { Fragment } from 'react'

const STAGES = [
  { id: 'failure', number: '01', label: 'Failure' },
  { id: 'investigation', number: '02', label: 'Investigation' },
  { id: 'repair', number: '03', label: 'Repair' },
  { id: 'verification', number: '04', label: 'Verify' },
]

function scrollToStage(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export default function PipelineNav({ statusById }) {
  return (
    <nav className="pipeline-nav" aria-label="Recovery pipeline">
      {STAGES.map((stage, index) => (
        <Fragment key={stage.id}>
          <button
            type="button"
            className={`pipeline-step pipeline-step--${statusById[stage.id] || 'pending'}`}
            onClick={() => scrollToStage(stage.id)}
          >
            <span className="pipeline-step__number">{stage.number}</span>
            <span className="pipeline-step__label">{stage.label}</span>
          </button>
          {index < STAGES.length - 1 && (
            <span className="pipeline-arrow" aria-hidden="true">
              &rarr;
            </span>
          )}
        </Fragment>
      ))}
    </nav>
  )
}
