import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProfileStrengthBar } from './ProfileStrengthBar'

const FILLED = {
  bio: 'Sales professional',
  skills: ['Negotiation'],
  years_of_experience: 4,
  location: 'Lagos',
}

const renderBar = (profile) =>
  render(
    <MemoryRouter>
      <ProfileStrengthBar profile={profile} />
    </MemoryRouter>
  )

describe('ProfileStrengthBar', () => {
  it('counts the CV as one of five equal parts', () => {
    renderBar({ ...FILLED, cvs: [] })

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '80')
  })

  it('sends someone who has filled in everything except the CV to where a CV is uploaded', () => {
    renderBar({ ...FILLED, cvs: [] })

    // The profile page has no CV upload, so neither the line nor the button may lead there.
    expect(screen.getByRole('link', { name: 'Upload a CV (PDF, up to 5MB)' }))
      .toHaveAttribute('href', '/candidate/dashboard/documents')
    expect(screen.getByRole('link', { name: 'Upload Your CV →' }))
      .toHaveAttribute('href', '/candidate/dashboard/documents')
    expect(screen.queryByRole('link', { name: 'Complete Your Profile →' })).not.toBeInTheDocument()
  })

  it('still sends someone with form fields missing to the profile page', () => {
    renderBar({ ...FILLED, bio: '', cvs: [] })

    expect(screen.getByRole('link', { name: 'Complete Your Profile →' }))
      .toHaveAttribute('href', '/candidate/profile')
    // The CV line still leads to the right place while the form is being finished.
    expect(screen.getByRole('link', { name: 'Upload a CV (PDF, up to 5MB)' }))
      .toHaveAttribute('href', '/candidate/dashboard/documents')
  })

  it('says all five items are needed to apply', () => {
    renderBar({ ...FILLED, cvs: [] })

    expect(screen.getByText(/You need all five items to apply for jobs/)).toBeInTheDocument()
  })

  it('has nothing left to ask for once the profile is complete', () => {
    renderBar({ ...FILLED, cvs: [{ id: 'c1' }] })

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByRole('link', { name: 'Edit Your Profile →' })).toBeInTheDocument()
    expect(screen.queryByText(/Upload a CV/)).not.toBeInTheDocument()
  })
})
