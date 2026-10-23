import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn() } }))

import api from '@/lib/api'
import SharedInterviewResultsPage from './SharedInterviewResultsPage'

const COMPLETED = {
  name: 'Ada Obi',
  current_title: 'Sales Manager',
  status: 'COMPLETED',
  completed_at: '2026-10-20T09:00:00Z',
  interview_score: 82,
  interview_assessment:
    'A confident communicator.\n\nStrengths:\n- Clear examples\n\nWeaknesses:\n- Light on numbers',
  cv_score: 74,
  cv_summary: 'Strong sales background.',
  cv_strengths: ['Distributor growth'],
  cv_weaknesses: ['No FMCG'],
  video_url: 'https://signed.example/video',
  questions: ['Tell me about managing distributors?', 'What was the hardest part?'],
  turns: [
    { speaker: 'AI', text: 'Tell me about managing distributors?' },
    { speaker: 'Candidate', text: 'I grew the network from twelve to forty.' },
    { speaker: 'AI', text: 'What was the hardest part?' },
    { speaker: 'Candidate', text: 'Credit control.' },
  ],
  transcript: null,
  transcript_note: null,
}
const PENDING = {
  name: 'Candidate 2',
  current_title: null,
  status: 'NOT_INVITED',
  questions: [],
  turns: [],
}

const RESULTS = {
  job_title: 'Regional Sales Manager',
  company_name: 'Colton Group',
  interview_focus: 'Probe distributor management.',
  expires_at: '2026-10-23T09:00:00Z',
  total_candidates: 3,
  completed_count: 1,
  truncated: false,
  candidates: [COMPLETED, PENDING],
}

function renderPage() {
  return render(
    <HelmetProvider>
      <MemoryRouter initialEntries={['/shared/interviews/tok123']}>
        <Routes>
          <Route path="/shared/interviews/:token" element={<SharedInterviewResultsPage />} />
        </Routes>
      </MemoryRouter>
    </HelmetProvider>
  )
}

const STRICT_NOTES = {
  rules_version: 'S2',
  rules_accepted_at: '2026-10-20T09:00:05Z',
  attempt: 1,
  ended: 'TOO_LONG_AWAY',
  ended_at: '2026-10-20T09:07:00Z',
  leaves: 2,
  away_seconds: 70,
  key_presses: 1,
  reloads: 0,
  events: [{ kind: 'ENDED', detail: 'TOO_LONG_AWAY', occurred_at: '2026-10-20T09:07:00Z', duration_seconds: null, attempt: 1, counted: false }],
  turns: [{ number: 1, kind: 'QUESTION', question: 'Tell us about a system.', answer: 'I built billing.', answered: true }],
}
const ENDED_EARLY = {
  name: 'Bola Ade',
  current_title: 'Account Manager',
  status: 'ENDED',
  completed_at: '2026-10-20T09:08:00Z',
  interview_score: null,
  interview_assessment: null,
  cv_score: 60,
  cv_summary: 'Solid.',
  cv_strengths: [],
  cv_weaknesses: [],
  video_url: 'https://signed.example/ended',
  questions: ['Tell us about a system.'],
  turns: [
    { speaker: 'AI', text: 'Tell us about a system.' },
    { speaker: 'Candidate', text: 'I built billing.' },
  ],
  transcript: null,
  transcript_note: null,
  strict: STRICT_NOTES,
}

describe('SharedInterviewResultsPage, strict interviews', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows an interview that ended early as ended, and opens to its recording, notes and answers', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [ENDED_EARLY] } })
    renderPage()

    expect(await screen.findByText('Ended early')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Bola Ade/ }))

    expect(screen.getByRole('region', { name: 'Interview notes' })).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('away from the interview screen for too long')
    expect(screen.getByText(/version S2, on/)).toBeInTheDocument()
    expect(screen.getByText('Interview conversation')).toBeInTheDocument()
    expect(document.querySelector('video')).toHaveAttribute('src', 'https://signed.example/ended')
  })

  it('shows no interview assessment for an interview that ended early, only the CV one', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [ENDED_EARLY] } })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Bola Ade/ }))

    expect(screen.queryByText('Interview assessment')).not.toBeInTheDocument()
    expect(screen.getByText('CV assessment')).toBeInTheDocument()
  })

  it('says the notes are not proof and that no decision was made for the client', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [ENDED_EARLY] } })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Bola Ade/ }))

    expect(screen.getByText(/They are not proof of anything/)).toBeInTheDocument()
    expect(screen.getByText(/no decision has been made for you/)).toBeInTheDocument()
  })

  it('shows a reinstated interview to the client as one clip per attempt', async () => {
    const reinstated = {
      ...ENDED_EARLY,
      recordings: [
        { attempt: 1, video_url: 'https://signed.example/one' },
        { attempt: 2, video_url: 'https://signed.example/two' },
      ],
      video_url: 'https://signed.example/two',
    }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [reinstated] } })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /Bola Ade/ }))

    expect(screen.getByText('Attempt 1')).toBeInTheDocument()
    expect(screen.getByText('Attempt 2, after the interview was reinstated')).toBeInTheDocument()
    expect([...document.querySelectorAll('video')].map((v) => v.getAttribute('src'))).toEqual([
      'https://signed.example/one',
      'https://signed.example/two',
    ])
  })

  it('shows the rules record and conduct notes on a finished strict interview too', async () => {
    const finished = { ...COMPLETED, strict: { ...STRICT_NOTES, ended: null, leaves: 0, away_seconds: 0, key_presses: 0, events: [] } }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [finished] } })
    renderPage()

    expect(await screen.findByRole('region', { name: 'Interview notes' })).toBeInTheDocument()
    expect(screen.getByText(/Nothing was noted: the candidate stayed on the screen/)).toBeInTheDocument()
  })

  it('shows no notes for a live interview', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [COMPLETED] } })
    renderPage()

    await screen.findByText('Ada Obi')
    expect(screen.queryByRole('region', { name: 'Interview notes' })).not.toBeInTheDocument()
  })
})

describe('SharedInterviewResultsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('asks the server for this link’s results', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    await screen.findByText('Regional Sales Manager')
    expect(api.get).toHaveBeenCalledWith('/api/v1/public/interview-results/tok123')
  })

  it('names the job and company, the progress and when the link expires', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    expect(await screen.findByText('Regional Sales Manager')).toBeInTheDocument()
    expect(screen.getByText('Colton Group')).toBeInTheDocument()
    expect(screen.getByText(/1 of 3 interviews completed/)).toBeInTheDocument()
    expect(screen.getByText(/This link expires on 23 October 2026/)).toBeInTheDocument()
  })

  it('shows what the AI was asked to cover', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    expect(await screen.findByText('What the AI was asked to cover')).toBeInTheDocument()
    expect(screen.getByText('Probe distributor management.')).toBeInTheDocument()
  })

  it('makes the questions the AI asked obvious: a numbered list, then each one set apart in the conversation', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    const heading = await screen.findByText('Questions the AI asked')
    const list = heading.closest('div').querySelector('ol')
    expect(within(list).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Tell me about managing distributors?',
      'What was the hardest part?',
    ])
    // In the conversation every AI turn is labelled and every answer is the candidate's.
    expect(screen.getAllByText('AI interviewer')).toHaveLength(2)
    expect(screen.getAllByText('Candidate').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('I grew the network from twelve to forty.')).toBeInTheDocument()
  })

  it('shows the recording and tells the viewer to reload if it stops', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    const { container } = renderPage()

    await screen.findByText('Questions the AI asked')
    expect(container.querySelector('video')).toHaveAttribute('src', 'https://signed.example/video')
    expect(screen.getByText(/Reload the page if it stops playing/)).toBeInTheDocument()
  })

  it('shows the interview assessment and the CV assessment side by side', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    expect(await screen.findByText('Interview assessment')).toBeInTheDocument()
    expect(screen.getByText('A confident communicator.')).toBeInTheDocument()
    expect(screen.getByText('Clear examples')).toBeInTheDocument()
    expect(screen.getByText('Light on numbers')).toBeInTheDocument()
    expect(screen.getByText('CV assessment')).toBeInTheDocument()
    expect(screen.getByText('Strong sales background.')).toBeInTheDocument()
    expect(screen.getByText('Distributor growth')).toBeInTheDocument()
    expect(screen.getByText('No FMCG')).toBeInTheDocument()
  })

  it('shows the interview score and the CV score on the candidate’s row', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    await screen.findByText('Ada Obi')
    expect(screen.getAllByText('82').length).toBeGreaterThan(0)
    expect(screen.getAllByText('74').length).toBeGreaterThan(0)
  })

  it('lists a candidate who has not interviewed, with a plain status and nothing to open', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    expect(await screen.findByText('Candidate 2')).toBeInTheDocument()
    expect(screen.getByText('Not interviewed yet')).toBeInTheDocument()
  })

  it('shows a transcript with no speaker labels as plain text with its note', async () => {
    const plain = {
      ...COMPLETED,
      questions: [],
      turns: [],
      transcript: 'Just the words the recording contains.',
      transcript_note: 'This transcript was produced automatically from the recording, so it has no speaker labels. Please check the video.',
    }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [plain] } })
    renderPage()

    expect(await screen.findByText('Just the words the recording contains.')).toBeInTheDocument()
    expect(screen.getByText(/no speaker labels/)).toBeInTheDocument()
    expect(screen.queryByText('Questions the AI asked')).not.toBeInTheDocument()
  })

  it('opens and closes a candidate’s details', async () => {
    const second = { ...COMPLETED, name: 'Chidi Okafor', interview_score: 60 }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [COMPLETED, second] } })
    renderPage()
    await screen.findByText('Ada Obi')
    // The first completed interview is open; the second is not.
    expect(screen.getAllByText('Questions the AI asked')).toHaveLength(1)

    fireEvent.click(screen.getByText('Chidi Okafor'))

    expect(screen.getAllByText('Questions the AI asked')).toHaveLength(2)
  })

  it('shortens a long interview focus and can show all of it', async () => {
    const long = 'Cover this. '.repeat(60)
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, interview_focus: long } })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Show all' }))

    expect(screen.getByRole('button', { name: 'Show less' })).toBeInTheDocument()
  })

  it('says when only some of a long list is shown', async () => {
    api.get.mockResolvedValueOnce({
      data: { ...RESULTS, total_candidates: 150, truncated: true, candidates: [COMPLETED] },
    })
    renderPage()

    expect(await screen.findByText(/Showing the first 1 of 150 candidates/)).toBeInTheDocument()
  })

  it('tells search engines to stay away', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()
    await screen.findByText('Ada Obi')

    await waitFor(() =>
      expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow')
    )
  })

  it.each([
    ['SHARE_LINK_EXPIRED', 'This link has expired'],
    ['SHARE_LINK_REVOKED', 'This link is no longer active'],
    ['SHARE_LINK_NOT_FOUND', 'This link is not valid'],
  ])('says clearly when a link does not open (%s)', async (code, title) => {
    api.get.mockRejectedValueOnce({ response: { data: { code } } })
    renderPage()

    expect(await screen.findByText(title)).toBeInTheDocument()
    expect(screen.queryByText('Regional Sales Manager')).not.toBeInTheDocument()
  })

  it('says something went wrong when the server cannot be reached', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    renderPage()

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
  })
})
