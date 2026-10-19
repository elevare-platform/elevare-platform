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
