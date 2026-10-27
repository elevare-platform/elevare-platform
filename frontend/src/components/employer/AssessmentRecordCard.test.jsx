import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import AssessmentRecordCard from './AssessmentRecordCard'

const RECORD = {
  reference: 'EL-1A2B3C4D',
  role: 'National Sales Manager',
  interview_date: '2026-10-20T09:17:40Z',
  duration_minutes: 18,
  interviewer: 'Elevare structured interview',
  top_strengths: ['Clear route to market', 'Owns the numbers', 'Builds distributors'],
  top_gaps: ['Light on supply chain'],
  claims_to_verify: ['Opened 40 outlets (unverified)'],
  reference_check_questions: ['Who led the distributor roll-out?'],
  panel_decision: null,
}

const reasonBox = () => screen.getByLabelText('Reason for the decision')
const choice = () => screen.getByLabelText(/^(Decision|Change the decision)$/)
const record = () => screen.getByRole('button', { name: 'Record decision' })

describe('AssessmentRecordCard, the record', () => {
  it('shows the header: reference, role, date, how long, and the interviewer', () => {
    render(<AssessmentRecordCard record={RECORD} />)

    expect(screen.getByTestId('record-reference')).toHaveTextContent('EL-1A2B3C4D')
    expect(screen.getByText('National Sales Manager')).toBeInTheDocument()
    expect(screen.getByText('20 Oct 2026')).toBeInTheDocument()
    expect(screen.getByText('18 min')).toBeInTheDocument()
    expect(screen.getByText('Elevare structured interview')).toBeInTheDocument()
  })

  it('numbers the top three strengths and gaps, and lists what to verify and ask referees', () => {
    render(<AssessmentRecordCard record={RECORD} />)

    const strengths = screen.getByText('Top three demonstrated strengths').parentElement
    expect(within(strengths).getAllByRole('listitem').map((li) => li.textContent)).toEqual(RECORD.top_strengths)
    expect(within(screen.getByText('Top three gaps or risks').parentElement).getByText('Light on supply chain')).toBeInTheDocument()
    expect(screen.getByText('Opened 40 outlets (unverified)')).toBeInTheDocument()
    expect(screen.getByText('Who led the distributor roll-out?')).toBeInTheDocument()
  })

  it('says plainly when there is nothing to list, and when the date or length was not recorded', () => {
    render(
      <AssessmentRecordCard
        record={{
          ...RECORD,
          interview_date: null,
          duration_minutes: null,
          top_strengths: [],
          top_gaps: [],
          claims_to_verify: [],
          reference_check_questions: [],
        }}
      />
    )

    expect(screen.getAllByText('Not recorded')).toHaveLength(2)
    expect(screen.getAllByText('None recorded.')).toHaveLength(2)
    expect(screen.getByText('None to check.')).toBeInTheDocument()
    expect(screen.getByText('None suggested.')).toBeInTheDocument()
  })

  it('shows no decision section at all without a way to decide, as on a shared link', () => {
    render(<AssessmentRecordCard record={{ ...RECORD, panel_decision: { decision: 'HOLD', label: 'Hold', rationale: 'Internal.', decided_by_name: 'Ada', decided_at: '2026-10-21T10:00:00Z' } }} />)

    expect(screen.queryByTestId('panel-decision')).not.toBeInTheDocument()
    expect(screen.queryByText('Internal.')).not.toBeInTheDocument()
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    const { container } = render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} />)

    expect(container.textContent).not.toMatch(/[–—!]/)
  })
})

describe('AssessmentRecordCard, the panel decision', () => {
  it('says no decision is recorded yet, and says it is a person\'s decision', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} />)

    expect(screen.getByTestId('no-decision')).toBeInTheDocument()
    expect(screen.getByText(/Recorded by a person, with the reason/)).toBeInTheDocument()
  })

  it('offers the four decisions of the client\'s pack and nothing that hires', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} />)

    expect(within(choice()).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Choose…', 'Strong shortlist', 'Shortlist', 'Hold', 'Do not shortlist',
    ])
  })

  it('cannot be recorded without a decision and a reason of a sentence or two', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} />)
    expect(record()).toBeDisabled()

    fireEvent.change(choice(), { target: { value: 'SHORTLIST' } })
    expect(record()).toBeDisabled() // no reason yet

    fireEvent.change(reasonBox(), { target: { value: 'ok' } })
    expect(record()).toBeDisabled() // too short to say anything

    fireEvent.change(reasonBox(), { target: { value: 'Strong on route to market.' } })
    expect(record()).toBeEnabled()
  })

  it('sends the decision and the trimmed reason, and clears the form', async () => {
    const onDecide = vi.fn().mockResolvedValue()
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} />)

    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    fireEvent.change(reasonBox(), { target: { value: '   Waiting for the references.  ' } })
    fireEvent.click(record())

    await waitFor(() => expect(onDecide).toHaveBeenCalledWith('HOLD', 'Waiting for the references.'))
    await waitFor(() => expect(reasonBox()).toHaveValue(''))
    expect(choice()).toHaveValue('')
  })

  it('shows the latest decision with its reason and who signed it off and when', () => {
    const decided = { decision: 'SHORTLIST', label: 'Shortlist', rationale: 'Good route to market.', decided_by_name: 'Ada Obi', decided_at: '2026-10-21T10:00:00Z' }
    render(<AssessmentRecordCard record={{ ...RECORD, panel_decision: decided }} onDecide={vi.fn()} />)

    const shown = screen.getByTestId('latest-decision')
    expect(shown).toHaveTextContent('Shortlist')
    expect(shown).toHaveTextContent('Good route to market.')
    expect(shown).toHaveTextContent('Signed off by Ada Obi on 21 Oct 2026')
    expect(screen.queryByTestId('no-decision')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Change the decision')).toBeInTheDocument()
  })

  it('shows the server\'s own words and keeps what was typed when recording fails', async () => {
    const onDecide = vi.fn().mockRejectedValue({
      response: { status: 422, data: { code: 'INTERVIEW_NOT_FINISHED', message: 'The interview has not finished yet, so there is nothing to decide on.' } },
    })
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} />)
    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    fireEvent.change(reasonBox(), { target: { value: 'Waiting for the references.' } })

    fireEvent.click(record())

    expect(await screen.findByRole('alert')).toHaveTextContent('nothing to decide on')
    expect(reasonBox()).toHaveValue('Waiting for the references.')
  })

  it('falls back to a plain line when the server gives no reason', async () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn().mockRejectedValue(new Error('network'))} />)
    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    fireEvent.change(reasonBox(), { target: { value: 'Waiting for the references.' } })

    fireEvent.click(record())

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Please try again.')
  })
})
