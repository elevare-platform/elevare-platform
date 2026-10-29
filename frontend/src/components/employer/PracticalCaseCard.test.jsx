import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import PracticalCaseCard from './PracticalCaseCard'

const row = (key, name, weight, rating, rationale = '') => ({ key, name, weight, rating, rationale })
const ROWS = [
  row('prioritisation', 'Prioritisation', 30, 4, 'Put distributors first.'),
  row('realism', 'Realism', 25, 3),
  row('measurement', 'Measurement', 20, 5),
  row('risk', 'Risk and contingency', 15, 2),
  row('clarity', 'Clarity of communication', 10, 4),
]
const COMPLETE = {
  question_number: 9, complete: true, score: 3.65, rows: ROWS, assessed_weight: 100, total_weight: 100, unassessed: [], summary: 'A workable plan.',
}

describe('PracticalCaseCard', () => {
  it('shows the criteria and ratings but no case total, and no incomplete notice, when the job’s switch has scores off', () => {
    const hidden = { ...COMPLETE, hidden: true, score: null, complete: false, unassessed: ['Risk'] }
    render(<PracticalCaseCard report={hidden} />)

    expect(screen.queryByTestId('practical-score')).not.toBeInTheDocument()
    expect(screen.queryByTestId('practical-incomplete')).not.toBeInTheDocument()
    expect(screen.queryByText(/No case score/)).not.toBeInTheDocument()
    expect(screen.getByText('Prioritisation')).toBeInTheDocument()
    expect(screen.getAllByText('4 of 5')).toHaveLength(2)
  })

  it('shows the case score out of 5 with one decimal, the criteria with their weights and ratings, and the summary', () => {
    render(<PracticalCaseCard report={COMPLETE} />)

    expect(screen.getByTestId('practical-score')).toHaveTextContent(/^3\.[67] \/ 5$/)
    expect(screen.getByText('Prioritisation')).toBeInTheDocument()
    expect(screen.getByText('30%')).toBeInTheDocument()
    expect(screen.getByText('Put distributors first.')).toBeInTheDocument()
    expect(screen.getAllByText('4 of 5')).toHaveLength(2)
    expect(screen.getByText('A workable plan.')).toBeInTheDocument()
  })

  it('says it is scored on its own and not part of the weighted score', () => {
    render(<PracticalCaseCard report={COMPLETE} />)

    expect(screen.getByText(/It is not part of the weighted score/)).toBeInTheDocument()
  })

  it('shows an incomplete case as incomplete, with no number, and names what was not covered', () => {
    const incomplete = {
      ...COMPLETE,
      complete: false,
      score: null,
      rows: [ROWS[0], row('realism', 'Realism', 25, null), ROWS[2], row('risk', 'Risk and contingency', 15, null), ROWS[4]],
      assessed_weight: 60,
      unassessed: ['Realism', 'Risk and contingency'],
    }
    render(<PracticalCaseCard report={incomplete} />)

    expect(screen.getByTestId('practical-incomplete')).toBeInTheDocument()
    expect(screen.queryByTestId('practical-score')).not.toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('3 of 5 criteria could be rated (not covered: Realism, Risk and contingency)')
    expect(screen.getByRole('note')).toHaveTextContent('No case score is given')
    expect(screen.getAllByText('Not covered')).toHaveLength(2)
  })

  it('leaves the summary out when there is none', () => {
    render(<PracticalCaseCard report={{ ...COMPLETE, summary: '' }} />)

    expect(screen.queryByText('A workable plan.')).not.toBeInTheDocument()
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const { container } = render(<PracticalCaseCard report={COMPLETE} />)

    expect(container.textContent).not.toMatch(/[–—!]/)
  })
})
