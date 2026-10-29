import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, within, act } from '@testing-library/react'

import ScorecardView from './ScorecardView'

// Ehi Okpepe's scorecard: weights 30, 25, 15, 15, 10 and 5; ratings 4, 4, 3.5, 3.5, 3.5 and 3.
const ROWS = [
  { name: 'Route-to-market and distributor development', weight: 30, key: true, rating: 4, points: 12, evidence: 'Strong localized knowledge (Lagos mapping, a corridor pilot).' },
  { name: 'Sales execution and territory management', weight: 25, key: true, rating: 4, points: 10, evidence: 'Focused on numeric distribution and strike rates.' },
  { name: 'Sales-force leadership', weight: 15, key: false, rating: 3.5, points: 5.25, evidence: 'Restructured teams after mergers.' },
  { name: 'Revenue, margin and collections management', weight: 15, key: false, rating: 3.5, points: 5.25, evidence: 'Collections within 30 days.' },
  { name: 'Forecasting and supply coordination', weight: 10, key: false, rating: 3.5, points: 3.5, evidence: 'Weekly demand planning meetings.' },
  { name: 'Reporting and performance analytics', weight: 5, key: false, rating: 3, points: 1.5, evidence: 'Tracked primary and secondary sales.' },
]
const CARD = {
  rows: ROWS,
  total_points: 37.5,
  max_points: 50,
  total_score: 75,
  practical_rating: 4,
  strengths: ['Excellent practical grasp of the Nigerian operating terrain.', 'Strong emphasis on strike rates.'],
  decision: 'Proceed to Final Interview / Offer Consideration',
  panel_decision: null,
  hidden: false,
}

const view = (props = {}) =>
  render(<ScorecardView scorecard={CARD} candidateName="Ehi Okpepe" role="National Sales Manager" date="2026-10-28T12:00:00Z" {...props} />)

describe('ScorecardView', () => {
  beforeEach(() => {
    window.print = vi.fn()
  })
  afterEach(() => {
    document.body.classList.remove('printing-scorecard')
  })

  it('lays out the heading as the printed scorecard does', () => {
    view()

    expect(screen.getByText('Elevare Human Solutions')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Interview Scorecard: National Sales Manager' })).toBeInTheDocument()
    expect(screen.getByText(/Candidate Name:/).parentElement).toHaveTextContent('Candidate Name: Ehi Okpepe')
    expect(screen.getByText(/Date of Evaluation:/).parentElement).toHaveTextContent('Date of Evaluation: October 28, 2026')
  })

  it('shows each competency with its weight, rating, weighted points and evidence', () => {
    view()

    const row = screen.getByText('Sales-force leadership').closest('tr')
    expect(row).toHaveTextContent('15%')
    expect(row).toHaveTextContent('3.5')
    expect(row).toHaveTextContent('5.25')
    expect(row).toHaveTextContent('Restructured teams after mergers.')
    expect(screen.getByText('Route-to-market and distributor development').closest('tr')).toHaveTextContent('12.0')
  })

  it('shows the total as points out of 50 with the 100-point total beside it', () => {
    view()

    const total = screen.getByTestId('scorecard-total')
    expect(total).toHaveTextContent('Total')
    expect(total).toHaveTextContent('100%')
    expect(total).toHaveTextContent('37.5 / 50 (75/100)')
  })

  it('shows the evaluation summary: practical rating, strengths and the human decision', () => {
    view()

    expect(screen.getByTestId('scorecard-practical')).toHaveTextContent('Practical Case Rating: 4.0 / 5')
    expect(screen.getByTestId('scorecard-strengths')).toHaveTextContent('Excellent practical grasp of the Nigerian operating terrain.')
    expect(within(screen.getByTestId('scorecard-strengths')).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByTestId('scorecard-decision')).toHaveTextContent('Human Decision: Proceed to Final Interview / Offer Consideration')
  })

  it('leaves out the whole Evaluation Summary when the job’s switch has it off, and keeps the table and the total', () => {
    view({ scorecard: { ...CARD, show_summary: false, practical_rating: null, strengths: [], decision: null } })

    expect(screen.queryByText('Evaluation Summary')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-practical')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-strengths')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-decision')).not.toBeInTheDocument()
    expect(screen.getByTestId('scorecard-total')).toHaveTextContent('37.5 / 50 (75/100)')
    expect(screen.getByText('Sales-force leadership')).toBeInTheDocument()
  })

  it('shows the Evaluation Summary when the server does not say (an older response)', () => {
    view()

    expect(screen.getByText('Evaluation Summary')).toBeInTheDocument()
  })

  it('puts the panel’s recorded band beside the wording, or alone when there is no wording', () => {
    const { unmount } = view({ scorecard: { ...CARD, panel_decision: 'Shortlist' } })
    expect(screen.getByTestId('scorecard-decision')).toHaveTextContent('Proceed to Final Interview / Offer Consideration (panel: Shortlist)')
    unmount()

    view({ scorecard: { ...CARD, decision: null, panel_decision: 'Shortlist' } })
    expect(screen.getByTestId('scorecard-decision')).toHaveTextContent('Human Decision: Shortlist')
  })

  it('leaves out the practical rating, strengths and decision lines when there are none', () => {
    view({ scorecard: { ...CARD, practical_rating: null, strengths: [], decision: null } })

    expect(screen.queryByTestId('scorecard-practical')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-strengths')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-decision')).not.toBeInTheDocument()
  })

  it('shows no points column, totals or practical rating when the job’s scores are switched off, but the ratings and evidence stay', () => {
    const hidden = {
      ...CARD,
      hidden: true,
      total_points: null,
      total_score: null,
      practical_rating: null,
      rows: ROWS.map((row) => ({ ...row, points: null })),
    }
    view({ scorecard: hidden })

    expect(screen.queryByText('Weighted Points')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-total')).not.toBeInTheDocument()
    expect(screen.queryByTestId('scorecard-practical')).not.toBeInTheDocument()
    const row = screen.getByText('Sales-force leadership').closest('tr')
    expect(row).toHaveTextContent('3.5')
    expect(row).toHaveTextContent('Restructured teams after mergers.')
    expect(screen.getByTestId('scorecard-decision')).toBeInTheDocument()
  })

  it('shows a competency that was not assessed as not assessed, with no points', () => {
    const rows = [...ROWS.slice(0, 5), { ...ROWS[5], rating: null, points: null, evidence: '' }]
    view({ scorecard: { ...CARD, rows } })

    const row = screen.getByText('Reporting and performance analytics').closest('tr')
    expect(row).toHaveTextContent('Not assessed')
  })

  it('shows nothing without a scorecard', () => {
    const { container } = view({ scorecard: null })

    expect(container).toBeEmptyDOMElement()
  })

  it('prints on request: a copy is added to the page, the print dialog opens, and it goes when the dialog closes', () => {
    view()
    expect(screen.queryByTestId('scorecard-print')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Download PDF/ }))

    expect(window.print).toHaveBeenCalledTimes(1)
    expect(document.body.classList.contains('printing-scorecard')).toBe(true)
    const printed = screen.getByTestId('scorecard-print')
    expect(printed.parentElement).toBe(document.body)
    expect(printed).toHaveTextContent('Interview Scorecard: National Sales Manager')

    act(() => {
      window.dispatchEvent(new Event('afterprint'))
    })

    expect(screen.queryByTestId('scorecard-print')).not.toBeInTheDocument()
    expect(document.body.classList.contains('printing-scorecard')).toBe(false)
  })
})
