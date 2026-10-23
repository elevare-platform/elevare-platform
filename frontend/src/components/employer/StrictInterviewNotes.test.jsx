import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import StrictInterviewNotes, { RecordingNotice } from './StrictInterviewNotes'

const STRICT = {
  rules_version: 'S2',
  rules_accepted_at: '2026-10-20T09:00:05Z',
  attempt: 1,
  ended: null,
  ended_at: null,
  leaves: 0,
  away_seconds: 0,
  key_presses: 0,
  reloads: 0,
  events: [],
  turns: [
    { number: 1, kind: 'QUESTION', question: 'Tell us about a system you designed.', answer: 'I built the billing service.', answered: true },
    { number: 1, kind: 'FOLLOW_UP', question: 'What would you change now?', answer: null, answered: true },
    { number: 2, kind: 'QUESTION', question: 'How did you handle an outage?', answer: null, answered: false },
  ],
}

const render_ = (over = {}) => render(<StrictInterviewNotes strict={{ ...STRICT, ...over }} />)

describe('StrictInterviewNotes', () => {
  it('shows nothing for a live interview, which has no such notes', () => {
    const { container } = render(<StrictInterviewNotes strict={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('says the notes are for review, not proof, and that no decision was made', () => {
    render_()

    const section = screen.getByRole('region', { name: 'Interview notes' })
    expect(section).toHaveTextContent('They are not proof of anything')
    expect(section).toHaveTextContent('no decision has been made for you')
  })

  it('shows the rules version the candidate accepted, with the date and time', () => {
    render_()

    expect(screen.getByText(/version S2, on/)).toBeInTheDocument()
    expect(screen.getByText(/2026/)).toBeInTheDocument()
  })

  it('says when no acceptance was recorded', () => {
    render_({ rules_version: null, rules_accepted_at: null })

    expect(screen.getByText(/not recorded/)).toBeInTheDocument()
  })

  it('shows the conduct summary', () => {
    render_({ leaves: 3, away_seconds: 41, reloads: 1, key_presses: 2 })

    const value = (label) => screen.getByText(label).previousSibling.textContent
    expect(value('Times they left the screen')).toBe('3')
    expect(value('Seconds away in total')).toBe('41')
    expect(value('Reloads')).toBe('1')
    expect(value('Keys noted')).toBe('2')
  })

  it('says so when nothing was noted', () => {
    render_()

    expect(screen.getByText(/Nothing was noted: the candidate stayed on the screen/)).toBeInTheDocument()
  })

  it('lists the timeline in plain sentences with the time of each event', () => {
    render_({
      events: [
        { kind: 'LEFT_PAGE', detail: 'FULLSCREEN', occurred_at: '2026-10-20T09:05:00Z', duration_seconds: 12, attempt: 1, counted: true },
        { kind: 'KEY_PRESS', detail: 'Escape', occurred_at: '2026-10-20T09:06:00Z', duration_seconds: null, attempt: 1, counted: false },
      ],
    })

    expect(screen.getByText('Left the interview screen (left full screen) for 12 s')).toBeInTheDocument()
    expect(screen.getByText('Pressed Esc')).toBeInTheDocument()
  })

  it('says why an interview ended early, as a note and in the timeline', () => {
    render_({
      ended: 'TOO_MANY_LEAVES',
      events: [{ kind: 'ENDED', detail: 'TOO_MANY_LEAVES', occurred_at: '2026-10-20T09:07:00Z', duration_seconds: null, attempt: 1, counted: false }],
    })

    expect(screen.getByRole('note')).toHaveTextContent('left the interview screen too many times')
    expect(screen.getByText('The interview ended because they left the interview screen too many times')).toBeInTheDocument()
  })

  it('says a stop was the candidates own choice', () => {
    render_({ ended: 'STOPPED' })

    expect(screen.getByRole('note')).toHaveTextContent('own choice')
  })

  it('has no ended note for an interview that finished', () => {
    render_()

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('marks which attempt each event belongs to after a reinstatement, and that the counts are for the latest', () => {
    render_({
      attempt: 2,
      events: [
        { kind: 'STOPPED', detail: 'STOPPED', occurred_at: '2026-10-20T09:07:00Z', duration_seconds: null, attempt: 1, counted: false },
        { kind: 'REINSTATED', detail: 'STOPPED', occurred_at: '2026-10-20T10:00:00Z', duration_seconds: null, attempt: 1, counted: false },
        { kind: 'KEY_PRESS', detail: 'F12', occurred_at: '2026-10-20T10:05:00Z', duration_seconds: null, attempt: 2, counted: false },
      ],
    })

    expect(screen.getByText(/This is attempt 2/)).toBeInTheDocument()
    expect(screen.getByText(/counts are for the latest attempt/)).toBeInTheDocument()
    expect(screen.getAllByText(/\[attempt 1\]/)).toHaveLength(2)
    expect(screen.getByText(/\[attempt 2\]/)).toBeInTheDocument()
    expect(screen.getByText(/reinstated so the candidate could carry on/)).toBeInTheDocument()
  })

  it('shows each answer under its question, a follow-up as a follow-up, and what is missing as missing', () => {
    render_()

    const answers = screen.getByText('Questions and answers').closest('div')
    const items = within(answers).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Question 1')
    expect(items[0]).toHaveTextContent('I built the billing service.')
    expect(items[1]).toHaveTextContent('Follow-up to question 1')
    expect(items[1]).toHaveTextContent('No answer could be written down. Please check the recording.')
    expect(items[2]).toHaveTextContent('Not answered.')
  })

  it('never calls anything cheating, a failure or a violation', () => {
    render_({ ended: 'TOO_LONG_AWAY' })

    expect(screen.getByRole('region', { name: 'Interview notes' }).textContent).not.toMatch(/cheat|violat|suspicio|caught|guilty/i)
  })
})

describe('RecordingNotice', () => {
  it('says the recording is being put together, and to check back', () => {
    render(<RecordingNotice strict={{ ...STRICT, recording_pending: true }} />)

    expect(screen.getByRole('status')).toHaveTextContent('being put together')
    expect(screen.getByRole('status')).toHaveTextContent('Check back in a minute')
  })

  it('says the video may be only part of the interview when joining never finished', () => {
    render(<RecordingNotice strict={{ ...STRICT, recording_partial: true }} />)

    expect(screen.getByRole('note')).toHaveTextContent('only part of this interview')
  })

  it('says nothing when the recording is whole, for a live interview, or when the server sent no flags', () => {
    const { container, rerender } = render(<RecordingNotice strict={STRICT} />)
    expect(container).toBeEmptyDOMElement()

    rerender(<RecordingNotice strict={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
