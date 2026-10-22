import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import InterviewFlow from './InterviewFlow'

function renderFlow(props = {}) {
  return render(
    <MemoryRouter>
      <InterviewFlow
        startSession={vi.fn()}
        requestUploadUrl={vi.fn()}
        completeUpload={vi.fn()}
        requestReset={vi.fn()}
        subtitle="Acme · Sales Executive"
        {...props}
      />
    </MemoryRouter>
  )
}

describe('InterviewFlow, the rules a candidate accepts before the interview', () => {
  it('shows the rules, in numbered groups', () => {
    renderFlow()
    const rules = screen.getByTestId('interview-rules')

    for (const heading of ['Before you start', 'During the interview', 'If something goes wrong', 'What you agree to']) {
      expect(within(rules).getByRole('heading', { name: heading })).toBeInTheDocument()
    }
    expect(within(rules).getByText(/Use one device and one browser/)).toBeInTheDocument()
    expect(within(rules).getByText(/you must be alone/i)).toBeInTheDocument()
    expect(within(rules).getByText(/You will be interviewed by an AI interviewer, not a person/)).toBeInTheDocument()
  })

  it('does not tell the candidate about tab or face monitoring, which does not exist yet', () => {
    renderFlow()
    const rules = screen.getByTestId('interview-rules')

    expect(within(rules).queryByText(/Stay on the interview page/)).not.toBeInTheDocument()
    expect(within(rules).queryByText(/is noted|are noted/)).not.toBeInTheDocument()
    expect(within(rules).queryByText(/Look at the screen/)).not.toBeInTheDocument()
  })

  it('will not start until the candidate has accepted the rules', () => {
    renderFlow()
    const start = screen.getByRole('button', { name: 'Start the interview' })

    expect(start).toBeDisabled()

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules and I accept them/ }))
    expect(start).toBeEnabled()

    fireEvent.click(screen.getByRole('checkbox', { name: /I have read these rules and I accept them/ }))
    expect(start).toBeDisabled()
  })

  it('still warns a candidate on their last attempt, and still shows the rules', () => {
    renderFlow({ sessionStartCount: 1 })

    expect(screen.getByText(/You've already started this interview once/)).toBeInTheDocument()
    expect(screen.getByTestId('interview-rules')).toBeInTheDocument()
  })

  it('shows no rules to a candidate who has used both attempts: they need a reset', () => {
    renderFlow({ sessionStartCount: 2 })

    expect(screen.getByText(/already used both attempts/)).toBeInTheDocument()
    expect(screen.queryByTestId('interview-rules')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start the interview' })).not.toBeInTheDocument()
  })
})
