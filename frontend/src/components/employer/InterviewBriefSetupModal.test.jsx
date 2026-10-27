import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { patch: vi.fn() } }))

import api from '@/lib/api'
import InterviewBriefSetupModal from './InterviewBriefSetupModal'

const BRIEF = 'Ask about distributed systems and past production incidents.'

function renderModal(props = {}) {
  const onSaved = vi.fn()
  const onClose = vi.fn()
  render(<InterviewBriefSetupModal jobId="job-1" onSaved={onSaved} onClose={onClose} {...props} />)
  return { onSaved, onClose }
}

const textbox = () => screen.getByRole('textbox')

describe('InterviewBriefSetupModal', () => {
  beforeEach(() => {
    api.patch.mockReset()
  })

  it('is the first-time setup when there is no brief yet', () => {
    renderModal()

    expect(screen.getByText('Set up interview')).toBeInTheDocument()
    expect(textbox()).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Save and enable' })).toBeInTheDocument()
    expect(screen.queryByText(/already started or finished/i)).not.toBeInTheDocument()
  })

  it('opens the existing brief for editing', () => {
    renderModal({ initialBrief: BRIEF })

    expect(screen.getByText('Edit interview brief')).toBeInTheDocument()
    expect(textbox()).toHaveValue(BRIEF)
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument()
    // Earlier candidates were asked the old version; say so.
    expect(screen.getByText(/already started or finished/i)).toBeInTheDocument()
  })

  it('cannot save until the brief has actually changed', () => {
    renderModal({ initialBrief: BRIEF })

    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()

    fireEvent.change(textbox(), { target: { value: `${BRIEF} Also ask about on-call.` } })

    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled()
  })

  it('saves the edited brief, trimmed, and hands back the updated job', async () => {
    const updatedJob = { id: 'job-1', interview_brief: 'New brief' }
    api.patch.mockResolvedValue({ data: updatedJob })
    const { onSaved } = renderModal({ initialBrief: BRIEF })

    fireEvent.change(textbox(), { target: { value: '  New brief  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updatedJob))
    expect(api.patch).toHaveBeenCalledWith('/api/v1/jobs/job-1', { interview_brief: 'New brief' })
  })

  it('will not save an empty brief', () => {
    renderModal({ initialBrief: BRIEF })

    fireEvent.change(textbox(), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(screen.getByText(/enter a brief/i)).toBeInTheDocument()
    expect(api.patch).not.toHaveBeenCalled()
  })

  it('shows the server error and keeps the dialog open when saving fails', async () => {
    api.patch.mockRejectedValue({ response: { data: { message: 'You do not have access to this job' } } })
    const { onSaved } = renderModal({ initialBrief: BRIEF })

    fireEvent.change(textbox(), { target: { value: 'Something else' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('You do not have access to this job')).toBeInTheDocument()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('never warns that saving takes the job offline', () => {
    renderModal({ initialBrief: BRIEF })

    expect(screen.queryByText(/offline/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/review/i)).not.toBeInTheDocument()
  })
})
