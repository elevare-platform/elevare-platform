import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import RescoreBar from './RescoreBar'

const STARTED = { scoring: 3, reparsing: 2, in_progress: 0, no_stored_file: 0, remaining: 4 }

function setup(props = {}) {
  const handlers = { onRescore: vi.fn(), onDismissResult: vi.fn() }
  render(<RescoreBar status={{ total: 7 }} working={false} result={null} {...handlers} {...props} />)
  return handlers
}

describe('RescoreBar', () => {
  it('shows nothing when everyone has a score, or the count is not known', () => {
    const { container, rerender } = render(
      <RescoreBar status={{ total: 0 }} working={false} result={null} onRescore={vi.fn()} />
    )
    expect(container).toBeEmptyDOMElement()

    rerender(<RescoreBar status={null} working={false} result={null} onRescore={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says how many candidates have no score and offers Rescore', () => {
    setup()

    expect(screen.getByText('7 candidates have no score')).toBeInTheDocument()
    expect(screen.getByText(/starts up to 25 at a time/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rescore' })).toBeInTheDocument()
  })

  it('uses the singular for one candidate', () => {
    setup({ status: { total: 1 } })
    expect(screen.getByText('1 candidate has no score')).toBeInTheDocument()
  })

  it('asks for a rescore of everyone who needs it when pressed', () => {
    const { onRescore } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Rescore' }))

    expect(onRescore).toHaveBeenCalledWith({})
  })

  it('cannot be pressed twice while it is starting', () => {
    setup({ working: true })

    const button = screen.getByRole('button', { name: 'Starting…' })
    expect(button).toBeDisabled()
  })

  it('says what a press did, and what is left', () => {
    setup({ result: STARTED })

    expect(screen.getByRole('status')).toHaveTextContent(
      'Started 5 candidates, 2 CVs are being read again. 4 still to do: press Rescore again to go on.'
    )
    expect(screen.getByRole('button', { name: 'Rescore' })).toBeInTheDocument()
  })

  it('when the last batch is started, says scores are on their way and drops the button', () => {
    setup({ status: { total: 0 }, result: { ...STARTED, remaining: 0 } })

    expect(screen.getByRole('status')).toHaveTextContent('Scores appear here as they finish')
    expect(screen.queryByRole('button', { name: 'Rescore' })).not.toBeInTheDocument()
  })

  it('lets the message be hidden', () => {
    const { onDismissResult } = setup({ status: { total: 0 }, result: STARTED })

    fireEvent.click(screen.getByRole('button', { name: 'Hide this message' }))

    expect(onDismissResult).toHaveBeenCalledTimes(1)
  })
})
