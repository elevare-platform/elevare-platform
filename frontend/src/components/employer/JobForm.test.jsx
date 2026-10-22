import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { JobForm } from './JobForm'

// Enough for the form to accept a submit.
const VALID = {
  title: 'Senior Backend Engineer',
  about_the_role: 'Build and run the APIs behind our products every day.',
  key_responsibilities: 'Design, build and maintain backend services for customers.',
  requirements: 'Strong Python skills and experience with FastAPI and Postgres.',
  location: 'Lagos, Nigeria',
  contract_type: 'FULL_TIME',
  work_location: 'LOCAL',
}

function renderForm(props = {}) {
  const onSubmit = vi.fn()
  render(<JobForm defaultValues={VALID} onSubmit={onSubmit} {...props} />)
  return onSubmit
}

describe('JobForm, publish as soon as it is approved', () => {
  it('offers the choice, and says what it does', () => {
    renderForm()

    const box = screen.getByRole('checkbox', { name: /publish it as soon as it is approved/i })
    expect(box).toBeInTheDocument()
    expect(box).not.toBeChecked()
    expect(screen.getByText(/does not have to come back|do not have to come back/i)).toBeInTheDocument()
    expect(screen.getByText(/plan's\s+limits still apply|plan's limits still apply/i)).toBeInTheDocument()
  })

  it('is off unless the employer ticks it, and the job is saved that way', async () => {
    const onSubmit = renderForm()

    fireEvent.click(screen.getByRole('button', { name: /save job/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0].publish_when_approved).toBe(false)
  })

  it('sends the choice with the job when it is ticked', async () => {
    const onSubmit = renderForm()

    fireEvent.click(screen.getByRole('checkbox', { name: /publish it as soon as it is approved/i }))
    fireEvent.click(screen.getByRole('button', { name: /save job/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0].publish_when_approved).toBe(true)
  })

  it('shows the saved choice when a job is edited', () => {
    renderForm({ defaultValues: { ...VALID, publish_when_approved: true } })

    expect(screen.getByRole('checkbox', { name: /publish it as soon as it is approved/i })).toBeChecked()
  })
})
