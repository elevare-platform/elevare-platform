import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'

vi.mock('@/components/layout/Navbar', () => ({ default: () => null }))
vi.mock('@/components/layout/Footer', () => ({ default: () => null }))
vi.mock('@/components/ui/FloatingWhatsApp', () => ({ FloatingWhatsApp: () => null }))

import PrivacyPage from './PrivacyPage'

function renderPage() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <PrivacyPage />
      </MemoryRouter>
    </HelmetProvider>
  )
}

describe('PrivacyPage, data sharing', () => {
  it('says a Public profile is shared with the clients who pay Elevare, through a link', () => {
    renderPage()

    const sharing = screen.getByRole('heading', { name: 'Data Sharing' }).parentElement
    expect(sharing).toHaveTextContent(/Public/)
    expect(sharing).toHaveTextContent(/clients: organisations that pay Elevare to find candidates for them/)
    expect(sharing).toHaveTextContent(/link that shows the profiles of selected candidates, including yours/)
  })

  it('tells the candidate that new profiles start Public and how to change it', () => {
    renderPage()

    const sharing = screen.getByRole('heading', { name: 'Data Sharing' }).parentElement
    expect(sharing).toHaveTextContent(/New profiles start as Public/)
    expect(sharing).toHaveTextContent(/"Applied only" or "Private"/)
  })
})
