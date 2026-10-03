import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgeLabel } from './TalentPoolFilters'

const daysAgo = (n) => new Date(Date.now() - n * 86_400_000).toISOString()

function renderLabel(createdDaysAgo, extra = {}) {
  return render(
    <AgeLabel profile={{ created_at: daysAgo(createdDaysAgo), ai_score: null, ...extra }} />
  )
}

describe('AgeLabel', () => {
  it('highlights candidates added this week with a NEW marker', () => {
    renderLabel(2)
    expect(screen.getByText('New')).toBeInTheDocument()
    expect(screen.getByText(/Added 2d ago/).closest('p')).toHaveAttribute('data-age', 'fresh')
  })

  it('keeps mid-age candidates plain', () => {
    renderLabel(14)
    expect(screen.queryByText('New')).not.toBeInTheDocument()
    expect(screen.getByText(/Added 2w ago/).closest('p')).toHaveAttribute('data-age', 'normal')
  })

  it('flags candidates older than a month, in words as well as colour', () => {
    renderLabel(60)
    expect(screen.getByText(/Added 2mo ago/).closest('p')).toHaveAttribute('data-age', 'stale')
  })

  it('shows when the score was computed, only for scored candidates', () => {
    renderLabel(10, { ai_score: 80, ai_score_computed_at: daysAgo(1) })
    expect(screen.getByText(/Scored 1d ago/)).toBeInTheDocument()
  })

  it('renders nothing without a created_at', () => {
    const { container } = render(<AgeLabel profile={{}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
