import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import WeightedScoreCard from './WeightedScoreCard'

const ROWS = [
  { name: 'Strategy', weight: 25, key: true, rating: 4 },
  { name: 'P&L', weight: 20, key: true, rating: 5 },
  { name: 'Route to market', weight: 20, key: false, rating: 3 },
  { name: 'Leadership', weight: 15, key: false, rating: 4 },
  { name: 'Brand', weight: 10, key: false, rating: 5 },
  { name: 'Execution', weight: 10, key: false, rating: 3 },
]

const COMPLETE = {
  rows: ROWS, points: 78, assessed_weight: 100, total_weight: 100, complete: true, score: 78,
  band: 'Shortlist', bands: { strong: 85, shortlist: 75, hold: 65 }, key_min_rating: 3, key_flags: [], unassessed: [],
}

const INCOMPLETE = {
  ...COMPLETE,
  rows: ROWS.map((row) => (row.name === 'P&L' ? { ...row, rating: null } : row)),
  points: 58, assessed_weight: 80, complete: false, score: null, band: null, unassessed: ['P&L'],
}

describe('WeightedScoreCard', () => {
  it('shows the total and the suggested band, marked provisional', () => {
    render(<WeightedScoreCard report={COMPLETE} />)

    expect(screen.getByTestId('weighted-total')).toHaveTextContent('78 / 100')
    expect(screen.getByTestId('weighted-band')).toHaveTextContent('Shortlist')
    expect(screen.getByText('Suggested band (provisional)')).toBeInTheDocument()
    expect(screen.queryByTestId('weighted-incomplete')).not.toBeInTheDocument()
  })

  it('lists every competency with its weight, key mark, rating and points', () => {
    render(<WeightedScoreCard report={COMPLETE} />)

    const strategy = screen.getByText('Strategy').closest('tr')
    expect(within(strategy).getByText('Key')).toBeInTheDocument()
    expect(strategy).toHaveTextContent('25%')
    expect(strategy).toHaveTextContent('4 of 5')
    expect(strategy).toHaveTextContent('20') // 4 / 5 x 25
    const route = screen.getByText('Route to market').closest('tr')
    expect(within(route).queryByText('Key')).not.toBeInTheDocument()
    expect(route).toHaveTextContent('12') // 3 / 5 x 20
  })

  it('says an incomplete score is incomplete, with what was assessed, and shows no number and no band', () => {
    render(<WeightedScoreCard report={INCOMPLETE} />)

    expect(screen.getByTestId('weighted-incomplete')).toHaveTextContent('Incomplete score')
    expect(screen.getByRole('note')).toHaveTextContent('58 of 80 weighted points could be assessed (not assessed: P&L)')
    expect(screen.getByRole('note')).toHaveTextContent('No full score and no band are given. A person decides')
    expect(screen.queryByTestId('weighted-total')).not.toBeInTheDocument()
    expect(screen.queryByTestId('weighted-band')).not.toBeInTheDocument()
    expect(screen.queryByText(/Suggested band/)).not.toBeInTheDocument()
  })

  it('shows a competency that was not assessed as such, never as a zero', () => {
    render(<WeightedScoreCard report={INCOMPLETE} />)

    const row = screen.getByText('P&L').closest('tr')
    expect(row).toHaveTextContent('Not assessed')
    expect(row).not.toHaveTextContent('0 of 5')
  })

  it('flags a key competency under the minimum and says the band is held, without rejecting', () => {
    render(
      <WeightedScoreCard
        report={{ ...COMPLETE, band: 'Hold for evidence', key_flags: ['Strategy'], rows: ROWS.map((r) => (r.name === 'Strategy' ? { ...r, rating: 2 } : r)) }}
      />
    )

    expect(screen.getByTestId('key-flags')).toHaveTextContent('Key competency rated under 3 of 5: Strategy.')
    expect(screen.getByTestId('key-flags')).toHaveTextContent('held at Hold for evidence until a person has looked at it')
    expect(screen.getByTestId('weighted-band')).toHaveTextContent('Hold for evidence')
  })

  it('says a person makes every decision', () => {
    render(<WeightedScoreCard report={COMPLETE} />)

    expect(screen.getByText(/a person makes every decision/)).toBeInTheDocument()
  })

  it('shows the written assessment under the table', () => {
    render(
      <WeightedScoreCard report={COMPLETE}>
        <p>A steady candidate.</p>
      </WeightedScoreCard>
    )

    expect(screen.getByText('A steady candidate.')).toBeInTheDocument()
  })

  it('shows a half point as one decimal and a whole point without one', () => {
    render(
      <WeightedScoreCard
        report={{ ...COMPLETE, rows: [{ name: 'A', weight: 33, key: false, rating: 3 }, { name: 'B', weight: 67, key: false, rating: 4 }] }}
      />
    )

    expect(screen.getByText('A').closest('tr')).toHaveTextContent('19.8')
    expect(screen.getByText('B').closest('tr')).toHaveTextContent('53.6')
  })

  it('shows a small Reviewed tag, and nothing about who or why, when a person set the score', () => {
    render(<WeightedScoreCard report={{ ...COMPLETE, score: 89, band: 'Strong shortlist', reviewed: true }} />)

    expect(screen.getByTestId('reviewed-tag')).toHaveTextContent('Reviewed')
    expect(screen.getByTestId('weighted-total')).toHaveTextContent('89 / 100')
    expect(screen.getByTestId('weighted-band')).toHaveTextContent('Strong shortlist')
  })

  it('shows the competencies and ratings but no total, no band, no points and no incomplete notice when the job’s switch has them off', () => {
    const hidden = { ...COMPLETE, hidden: true, score: null, band: null, points: 0, bands: {} }
    render(<WeightedScoreCard report={hidden}>{<p>The written assessment.</p>}</WeightedScoreCard>)

    expect(screen.queryByTestId('weighted-total')).not.toBeInTheDocument()
    expect(screen.queryByTestId('weighted-band')).not.toBeInTheDocument()
    expect(screen.queryByTestId('weighted-incomplete')).not.toBeInTheDocument()
    expect(screen.queryByText('Points')).not.toBeInTheDocument()
    expect(screen.queryByText(/Suggested band|provisional/)).not.toBeInTheDocument()
    const strategy = screen.getByText('Strategy').closest('tr')
    expect(strategy).toHaveTextContent('25%')
    expect(strategy).toHaveTextContent('4 of 5')
    expect(screen.getByText('The written assessment.')).toBeInTheDocument()
  })

  it('shows no tag for the system’s own score', () => {
    render(<WeightedScoreCard report={COMPLETE} />)

    expect(screen.queryByTestId('reviewed-tag')).not.toBeInTheDocument()
  })

  it('drops the line that says a low key competency holds the band once a person has set the score', () => {
    const flagged = { ...COMPLETE, key_flags: ['Strategy'] }
    const { rerender } = render(<WeightedScoreCard report={flagged} />)
    expect(screen.getByTestId('key-flags')).toHaveTextContent('held at Hold for evidence')

    rerender(<WeightedScoreCard report={{ ...flagged, reviewed: true }} />)

    expect(screen.getByTestId('key-flags')).toHaveTextContent('Key competency rated under 3 of 5: Strategy.')
    expect(screen.getByTestId('key-flags')).not.toHaveTextContent('held at Hold for evidence')
  })
})
