import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { post: vi.fn() } }))

import api from '@/lib/api'
import InviteByEmailForm from './InviteByEmailForm'

const box = () => screen.getByRole('textbox', { name: "Candidate's email address" })
const send = () => screen.getByRole('button', { name: /Send interview/ })

function setup() {
  const onInvited = vi.fn()
  render(<InviteByEmailForm jobId="job-1" onInvited={onInvited} />)
  return { onInvited }
}

describe('InviteByEmailForm', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says no CV is needed and the address goes on the list', () => {
    setup()

    expect(screen.getByRole('form', { name: 'Invite by email' })).toHaveTextContent('No CV needed')
    expect(send()).toBeDisabled()
  })

  it('sends the address to the job, tells the employer, clears the box and refreshes the list', async () => {
    api.post.mockResolvedValue({ data: { sent: true, reason: null, talent_pool_profile_id: 'p-1' } })
    const { onInvited } = setup()

    fireEvent.change(box(), { target: { value: '  Ada@Example.com ' } })
    fireEvent.click(send())

    expect(await screen.findByRole('status')).toHaveTextContent('Interview link sent to ada@example.com.')
    expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/jobs/job-1/invite-by-email', { email: 'Ada@Example.com' })
    expect(box()).toHaveValue('')
    expect(onInvited).toHaveBeenCalledTimes(1)
  })

  it('says the address is on the list but the link was not sent, with the server reason', async () => {
    api.post.mockResolvedValue({ data: { sent: false, reason: 'Not enough credits', talent_pool_profile_id: 'p-1' } })
    const { onInvited } = setup()

    fireEvent.change(box(), { target: { value: 'ada@example.com' } })
    fireEvent.click(send())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('ada@example.com is on the interview list, but the link was not sent: Not enough credits')
    expect(onInvited).toHaveBeenCalledTimes(1) // the row is there now, so the list must refresh
    expect(box()).toHaveValue('ada@example.com') // kept, to try again
  })

  it('catches an obvious typo before asking the server', () => {
    setup()

    fireEvent.change(box(), { target: { value: 'not-an-email' } })
    fireEvent.click(send())

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email address.')
    expect(api.post).not.toHaveBeenCalled()
  })

  it("shows the server's message when it refuses (switched off, no access), and does not refresh", async () => {
    api.post.mockRejectedValue({ response: { status: 503, data: { message: 'AI interviews are temporarily unavailable. Please try again later.' } } })
    const { onInvited } = setup()

    fireEvent.change(box(), { target: { value: 'ada@example.com' } })
    fireEvent.click(send())

    expect(await screen.findByRole('alert')).toHaveTextContent('temporarily unavailable')
    expect(onInvited).not.toHaveBeenCalled()
  })

  it('says something plain when the server cannot be reached', async () => {
    api.post.mockRejectedValue(new Error('Network Error'))
    setup()

    fireEvent.change(box(), { target: { value: 'ada@example.com' } })
    fireEvent.click(send())

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Please try again.')
  })

  it('sends once when pressed twice quickly', async () => {
    let release
    api.post.mockReturnValue(new Promise((resolve) => { release = () => resolve({ data: { sent: true } }) }))
    setup()

    fireEvent.change(box(), { target: { value: 'ada@example.com' } })
    const button = send()
    fireEvent.click(button)
    fireEvent.click(button)
    release()

    await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument())
    expect(api.post).toHaveBeenCalledTimes(1)
  })
})
