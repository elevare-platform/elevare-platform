import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { patch: vi.fn() } }))

import api from '@/lib/api'
import CandidateNameEditor from './CandidateNameEditor'

function setup(props = {}) {
  const onSaved = vi.fn()
  render(<CandidateNameEditor profileId="p-1" name="Regional Sales Manager" onSaved={onSaved} {...props} />)
  return { onSaved }
}

const openEditor = () => fireEvent.click(screen.getByRole('button', { name: 'Correct the name' }))
const input = () => screen.getByLabelText("Candidate's name")

describe('CandidateNameEditor', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the name with a pencil to correct it', () => {
    setup()

    expect(screen.getByText('Regional Sales Manager')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Correct the name' })).toBeInTheDocument()
    expect(screen.queryByText('(corrected)')).not.toBeInTheDocument()
  })

  it('opens with the name as it is now, and saves the new one', async () => {
    api.patch.mockResolvedValueOnce({ data: { id: 'p-1', candidate_name: 'Lateef Jakande', name_overridden: true } })
    const { onSaved } = setup()

    openEditor()
    expect(input()).toHaveValue('Regional Sales Manager')
    fireEvent.change(input(), { target: { value: '  Lateef Jakande ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save name' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith({ id: 'p-1', candidate_name: 'Lateef Jakande', name_overridden: true }))
    expect(api.patch).toHaveBeenCalledWith('/api/v1/talent-pool/p-1/name', { name: 'Lateef Jakande' })
    expect(screen.queryByLabelText("Candidate's name")).not.toBeInTheDocument()
  })

  it('does not save an unchanged name, and does nothing on cancel', () => {
    setup()

    openEditor()
    expect(screen.getByRole('button', { name: 'Save name' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(api.patch).not.toHaveBeenCalled()
    expect(screen.getByText('Regional Sales Manager')).toBeInTheDocument()
  })

  it('refuses a name over 120 characters before asking the server', () => {
    setup()

    openEditor()
    fireEvent.change(input(), { target: { value: 'x'.repeat(121) } })

    expect(screen.getByText('Use 120 characters or fewer.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save name' })).toBeDisabled()
  })

  it('says a typed name was corrected, and offers to go back to the CV’s name', async () => {
    api.patch.mockResolvedValueOnce({ data: { id: 'p-1', candidate_name: 'Regional Sales Manager', name_overridden: false } })
    const { onSaved } = setup({ name: 'Lateef Jakande', overridden: true })

    expect(screen.getByText('(corrected)')).toBeInTheDocument()
    openEditor()
    fireEvent.click(screen.getByRole('button', { name: 'Use the name from the CV' }))

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/api/v1/talent-pool/p-1/name', { name: null }))
    expect(onSaved).toHaveBeenCalled()
  })

  it('shows the server’s words when it refuses, and keeps the box open', async () => {
    api.patch.mockRejectedValueOnce({ response: { data: { message: 'You don’t have access to change this candidate’s name.' } } })
    setup()

    openEditor()
    fireEvent.change(input(), { target: { value: 'Someone' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save name' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('access to change this candidate')
    expect(input()).toBeInTheDocument()
  })

  it('says the server could not be reached when there is no answer', async () => {
    api.patch.mockRejectedValueOnce(new Error('network'))
    setup()

    openEditor()
    fireEvent.change(input(), { target: { value: 'Someone' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save name' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not reach the server')
  })

  it('shows the fallback when there is no name at all', () => {
    setup({ name: null, fallback: 'Unnamed Candidate' })

    expect(screen.getByText('Unnamed Candidate')).toBeInTheDocument()
  })
})
