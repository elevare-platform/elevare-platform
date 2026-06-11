import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import NotFoundPage from './NotFoundPage'

function renderNotFound() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    </HelmetProvider>
  )
}

describe('NotFoundPage', () => {
  it('renders 404 headline', () => {
    renderNotFound()
    expect(screen.getByText('404')).toBeInTheDocument()
    expect(screen.getByText(/page not found/i)).toBeInTheDocument()
  })

  it('renders homepage and browse jobs links', () => {
    renderNotFound()
    expect(screen.getByRole('link', { name: /back to homepage/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /browse jobs/i })).toHaveAttribute('href', '/jobs')
  })
})
