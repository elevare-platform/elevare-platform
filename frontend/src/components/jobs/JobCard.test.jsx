import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { JobCard, getJobActions } from './JobCard'
import { disabledNote } from '@/lib/jobDisabled'

const JOB = {
  id: 'job-1',
  title: 'Sales Executive',
  company_name: 'Acme',
  location: 'Lagos',
  contract_type: 'FULL_TIME',
  status: 'DISABLED',
  disabled_reason: 'APPLICANT_LIMIT',
  application_count: 3,
  created_at: '2026-10-01T10:00:00Z',
}

function renderEmployerCard(job, handlers = {}) {
  return render(
    <MemoryRouter>
      <JobCard job={job} variant="employer" {...handlers} />
    </MemoryRouter>
  )
}

describe('getJobActions', () => {
  it('offers a switched-off job a way back, and nothing that only makes sense for a live or draft job', () => {
    const actions = getJobActions('DISABLED')

    expect(actions.republish).toBe(true)
    expect(actions.publish).toBe(false)
    expect(actions.close).toBe(false)
    expect(actions.edit).toBe(false)
    expect(actions.delete).toBe(false)
  })

  it('does not offer re-publish for any other status', () => {
    for (const status of ['DRAFT', 'ACTIVE', 'CLOSED']) {
      expect(getJobActions(status).republish).toBe(false)
    }
  })
})

describe('disabledNote', () => {
  it('says why the job was switched off, that the applicants are kept, and what to do', () => {
    expect(disabledNote({ disabled_reason: 'APPLICANT_LIMIT' })).toMatch(/most applicants your plan allows/)
    expect(disabledNote({ disabled_reason: 'EXPIRED' })).toMatch(/30 days/)
    expect(disabledNote({ disabled_reason: 'PLAN_LAPSED' })).toMatch(/plan has ended/)
    for (const reason of ['APPLICANT_LIMIT', 'EXPIRED', 'PLAN_LAPSED']) {
      const note = disabledNote({ disabled_reason: reason })
      expect(note).toMatch(/applicants are kept/)
      expect(note).toMatch(/Upgrade your plan to re-publish/)
    }
  })

  it('still reads properly when the reason is not known', () => {
    expect(disabledNote({})).toMatch(/^Switched off\. Your applicants are kept/)
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    for (const reason of ['APPLICANT_LIMIT', 'EXPIRED', 'PLAN_LAPSED', undefined]) {
      expect(disabledNote({ disabled_reason: reason })).not.toMatch(/[–—!]/)
    }
  })
})

describe('JobCard for the employer, on a switched-off job', () => {
  it('shows why it was switched off and a Re-publish button that publishes it', () => {
    const onPublish = vi.fn()
    renderEmployerCard(JOB, { onPublish })

    expect(screen.getByText(/it reached the most applicants your plan allows/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Re-publish' }))

    expect(onPublish).toHaveBeenCalledWith(JOB)
  })

  it('still lets the employer see the applicants it kept', () => {
    renderEmployerCard(JOB)

    expect(screen.getByRole('link', { name: /View Applicants/ })).toHaveAttribute(
      'href',
      '/employer/jobs/job-1/applicants'
    )
  })

  it('shows no Re-publish button on a live job', () => {
    renderEmployerCard({ ...JOB, status: 'ACTIVE', disabled_reason: null })

    expect(screen.queryByRole('button', { name: 'Re-publish' })).not.toBeInTheDocument()
  })
})
