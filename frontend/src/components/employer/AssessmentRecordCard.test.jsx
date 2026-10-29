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

  it('falls back to a plain line when the server answers with no reason', async () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn().mockRejectedValue({ response: { status: 500, data: {} } })} />)
    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    fireEvent.change(reasonBox(), { target: { value: 'Waiting for the references.' } })

    fireEvent.click(record())

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Please try again.')
  })

  it('says the server could not be reached when there was no answer at all', async () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn().mockRejectedValue(new Error('network'))} />)
    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    fireEvent.change(reasonBox(), { target: { value: 'Waiting for the references.' } })

    fireEvent.click(record())

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach the server')
  })

  it('says what is missing while the button is off', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} />)
    expect(screen.getByTestId('why-disabled')).toHaveTextContent('Choose a decision.')

    fireEvent.change(choice(), { target: { value: 'SHORTLIST' } })
    expect(screen.getByTestId('why-disabled')).toHaveTextContent('Write a reason of at least 10 characters (10 more).')

    fireEvent.change(reasonBox(), { target: { value: 'Good.' } })
    expect(screen.getByTestId('why-disabled')).toHaveTextContent('(5 more)')

    fireEvent.change(reasonBox(), { target: { value: 'Good route to market.' } })
    expect(screen.queryByTestId('why-disabled')).not.toBeInTheDocument()
  })

  it('does not let a decision be recorded before the interview has finished, and says why', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} blockedReason="The interview has not finished yet, so there is nothing to decide on." />)
    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    fireEvent.change(reasonBox(), { target: { value: 'Waiting for the references.' } })

    expect(record()).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('nothing to decide on')
  })
})

describe('AssessmentRecordCard, a suggested band', () => {
  const props = { suggestedBand: 'Shortlist', suggestedScore: 78 }

  it('shows the suggestion and offers to accept it or to choose differently, before any form', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} {...props} />)

    expect(screen.getByTestId('suggested-decision')).toHaveTextContent('Shortlist, score 78 of 100')
    expect(screen.getByRole('button', { name: 'Accept this suggestion' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Choose a different decision' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Record decision' })).not.toBeInTheDocument()
  })

  it('records the suggestion in one click, with a reason that says it was agreed', async () => {
    const onDecide = vi.fn().mockResolvedValue()
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} {...props} />)

    fireEvent.click(screen.getByRole('button', { name: 'Accept this suggestion' }))

    await waitFor(() =>
      expect(onDecide).toHaveBeenCalledWith('SHORTLIST', 'Agreed with the suggested band: Shortlist (score 78 of 100).')
    )
  })

  it('maps each band to its decision', async () => {
    const onDecide = vi.fn().mockResolvedValue()
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} suggestedBand="Hold for evidence" suggestedScore={null} />)

    fireEvent.click(screen.getByRole('button', { name: 'Accept this suggestion' }))

    await waitFor(() => expect(onDecide).toHaveBeenCalledWith('HOLD', 'Agreed with the suggested band: Hold for evidence.'))
  })

  it('opens the form to choose differently, and records a different decision with its reason and a note that it differs', async () => {
    const onDecide = vi.fn().mockResolvedValue()
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} {...props} />)

    fireEvent.click(screen.getByRole('button', { name: 'Choose a different decision' }))
    fireEvent.change(choice(), { target: { value: 'HOLD' } })
    expect(screen.getByTestId('differs-note')).toHaveTextContent('This differs from the suggestion (Shortlist)')
    fireEvent.change(reasonBox(), { target: { value: 'Waiting for the references.' } })
    fireEvent.click(record())

    await waitFor(() =>
      expect(onDecide).toHaveBeenCalledWith('HOLD', 'Waiting for the references. (Differs from the suggested band: Shortlist.)')
    )
  })

  it('records the same decision as the suggestion by the form with the reason as typed', async () => {
    const onDecide = vi.fn().mockResolvedValue()
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} {...props} />)

    fireEvent.click(screen.getByRole('button', { name: 'Choose a different decision' }))
    fireEvent.change(choice(), { target: { value: 'SHORTLIST' } })
    fireEvent.change(reasonBox(), { target: { value: 'Agree, with the references to come.' } })
    fireEvent.click(record())

    await waitFor(() => expect(onDecide).toHaveBeenCalledWith('SHORTLIST', 'Agree, with the references to come.'))
    expect(screen.queryByTestId('differs-note')).not.toBeInTheDocument()
  })

  it('cannot be accepted before the interview has finished', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} {...props} blockedReason="The interview has not finished yet, so there is nothing to decide on." />)

    expect(screen.getByRole('button', { name: 'Accept this suggestion' })).toBeDisabled()
  })

  it('shows the server\'s words when accepting fails, and leaves the choice open', async () => {
    const onDecide = vi.fn().mockRejectedValue({ response: { status: 403, data: { message: 'You do not have access to this job' } } })
    render(<AssessmentRecordCard record={RECORD} onDecide={onDecide} {...props} />)

    fireEvent.click(screen.getByRole('button', { name: 'Accept this suggestion' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('You do not have access to this job')
    expect(screen.getByRole('button', { name: 'Accept this suggestion' })).toBeEnabled()
  })

  it('after a decision, says whether it matches the suggestion, and still lets it be changed', () => {
    const decided = { decision: 'SHORTLIST', label: 'Shortlist', rationale: 'Agreed.', decided_by_name: 'Ada Obi', decided_at: '2026-10-21T10:00:00Z' }
    const { rerender } = render(<AssessmentRecordCard record={{ ...RECORD, panel_decision: decided }} onDecide={vi.fn()} {...props} />)

    expect(screen.getByTestId('latest-decision')).toHaveTextContent('Matches the suggestion.')
    expect(screen.getByLabelText('Change the decision')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Accept this suggestion' })).not.toBeInTheDocument()

    rerender(<AssessmentRecordCard record={{ ...RECORD, panel_decision: { ...decided, decision: 'HOLD', label: 'Hold' } }} onDecide={vi.fn()} {...props} />)
    expect(screen.getByTestId('latest-decision')).toHaveTextContent('Differs from the suggestion (Shortlist).')
  })

  it('shows the top three gaps or risks, and leaves them out when the job’s switch has them off', () => {
    const { rerender } = render(<AssessmentRecordCard record={RECORD} />)
    expect(screen.getByText('Top three gaps or risks')).toBeInTheDocument()
    expect(screen.getByText('Light on supply chain')).toBeInTheDocument()

    rerender(<AssessmentRecordCard record={{ ...RECORD, top_gaps: [] }} gapsHidden />)

    expect(screen.queryByText('Top three gaps or risks')).not.toBeInTheDocument()
    expect(screen.queryByText('None recorded.')).not.toBeInTheDocument()
    expect(screen.getByText('Top three demonstrated strengths')).toBeInTheDocument()
    expect(screen.getByText('Opened 40 outlets (unverified)')).toBeInTheDocument()
  })

  it('says the panel decides when there is no suggested band, and shows the form at once', () => {
    render(<AssessmentRecordCard record={RECORD} onDecide={vi.fn()} suggestedBand={null} />)

    expect(screen.getByTestId('no-suggestion')).toHaveTextContent('the panel decides')
    expect(record()).toBeInTheDocument()
  })
})
