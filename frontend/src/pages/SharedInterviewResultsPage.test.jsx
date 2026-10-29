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

const openTab = (name) => fireEvent.click(screen.getByRole('tab', { name }))

function renderPage(url = '/shared/interviews/tok123') {
  return render(
    <HelmetProvider>
      <MemoryRouter initialEntries={[url]}>
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

    // Nobody finished, so the one that ended early opens on its own.
    expect(await screen.findByRole('region', { name: 'Interview notes' })).toBeInTheDocument()
    expect(screen.getAllByText('Ended early').length).toBeGreaterThan(0)
    expect(screen.getByRole('note')).toHaveTextContent('away from the interview screen for too long')
    expect(screen.getByText(/version S2, on/)).toBeInTheDocument()
    expect(document.querySelector('video')).toHaveAttribute('src', 'https://signed.example/ended')
    openTab('Conversation')
    expect(screen.getByText('Interview conversation')).toBeInTheDocument()
  })

  it('shows no interview assessment for an interview that ended early, only the CV one', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [ENDED_EARLY] } })
    renderPage()
    await screen.findByText('CV assessment')

    expect(screen.queryByText('Interview assessment')).not.toBeInTheDocument()
  })

  it('says the notes are not proof and that no decision was made for the client', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [ENDED_EARLY] } })
    renderPage()
    await screen.findByRole('region', { name: 'Interview notes' })

    expect(screen.getByText(/They are not proof of anything/)).toBeInTheDocument()
    expect(screen.getByText(/no decision has been made for you/)).toBeInTheDocument()
  })

  it('shows the client the weighted table with the provisional band, or an incomplete score with no band', async () => {
    const rows = [
      { name: 'Strategy', weight: 60, key: true, rating: 4 },
      { name: 'P&L', weight: 40, key: false, rating: 3 },
    ]
    const base = { bands: { strong: 85, shortlist: 75, hold: 65 }, key_min_rating: 3, key_flags: [], total_weight: 100 }
    const complete = { ...base, rows, points: 72, assessed_weight: 100, complete: true, score: 72, band: 'Hold for evidence', unassessed: [] }
    const incomplete = {
      ...base, rows: [rows[0], { ...rows[1], rating: null }], points: 48, assessed_weight: 60, complete: false,
      score: null, band: null, unassessed: ['P&L'],
    }
    api.get.mockResolvedValueOnce({
      data: {
        ...RESULTS,
        candidates: [{ ...ENDED_EARLY, status: 'COMPLETED', interview_score: 72, interview_assessment: 'A steady candidate.', score_report: complete }],
      },
    })
    const first = renderPage()
    // A completed interview is open when the page loads; its scores are on the Scores tab.
    await screen.findByRole('tab', { name: 'Scores' })
    openTab('Scores')
    expect(screen.getByTestId('weighted-band')).toHaveTextContent('Hold for evidence')
    first.unmount()

    api.get.mockResolvedValueOnce({
      data: {
        ...RESULTS,
        candidates: [{ ...ENDED_EARLY, status: 'COMPLETED', interview_score: null, interview_assessment: 'INCOMPLETE SCORE.', score_report: incomplete }],
      },
    })
    renderPage()
    await screen.findByRole('tab', { name: 'Scores' })
    openTab('Scores')
    expect(screen.getByTestId('weighted-incomplete')).toBeInTheDocument()
    expect(screen.queryByTestId('weighted-band')).not.toBeInTheDocument()
  })

  it('shows the client the practical case on its own, apart from the weighted score', async () => {
    const practical = {
      question_number: 9, complete: true, score: 4, assessed_weight: 100, total_weight: 100, unassessed: [], summary: '',
      rows: [
        { key: 'prioritisation', name: 'Prioritisation', weight: 30, rating: 4, rationale: '' },
        { key: 'realism', name: 'Realism', weight: 25, rating: 4, rationale: '' },
        { key: 'measurement', name: 'Measurement', weight: 20, rating: 4, rationale: '' },
        { key: 'risk', name: 'Risk and contingency', weight: 15, rating: 4, rationale: '' },
        { key: 'clarity', name: 'Clarity of communication', weight: 10, rating: 4, rationale: '' },
      ],
    }
    api.get.mockResolvedValueOnce({
      data: { ...RESULTS, candidates: [{ ...ENDED_EARLY, status: 'COMPLETED', interview_score: 72, interview_assessment: 'Fine.', practical_case: practical }] },
    })
    renderPage()

    await screen.findByRole('tab', { name: 'Scores' })
    openTab('Scores')
    expect(screen.getByTestId('practical-score')).toHaveTextContent('4.0 / 5')
    expect(screen.queryByTestId('weighted-total')).not.toBeInTheDocument()
  })

  it('shows the client the assessment record, and never a decision form', async () => {
    const record = {
      reference: 'EL-1A2B3C4D', role: 'Sales Manager', interview_date: '2026-10-20T09:17:40Z', duration_minutes: 18,
      interviewer: 'Elevare structured interview', top_strengths: ['Clear route to market'], top_gaps: [],
      claims_to_verify: [], reference_check_questions: ['Who led the roll-out?'], panel_decision: null,
    }
    api.get.mockResolvedValueOnce({
      data: { ...RESULTS, candidates: [{ ...ENDED_EARLY, status: 'COMPLETED', interview_score: 72, interview_assessment: 'Fine.', record }] },
    })
    renderPage()

    await screen.findByRole('tab', { name: 'Assessment record' })
    openTab('Assessment record')
    expect(screen.getByTestId('record-reference')).toHaveTextContent('EL-1A2B3C4D')
    expect(screen.getByText('Who led the roll-out?')).toBeInTheDocument()
    expect(screen.queryByTestId('panel-decision')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Record decision' })).not.toBeInTheDocument()
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

    expect(await screen.findByText('Attempt 1')).toBeInTheDocument()
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

    await screen.findByText('Interview assessment')
    expect(screen.queryByRole('region', { name: 'Interview notes' })).not.toBeInTheDocument()
  })
})

const person = (name, extra = {}) => ({ ...COMPLETED, name, ...extra })
const rowNames = () => within(screen.getByRole('list', { name: 'Candidates' })).getAllByRole('listitem').map((li) => li.textContent)

describe('SharedInterviewResultsPage, the list of candidates', () => {
  beforeEach(() => vi.clearAllMocks())

  const THREE = [
    person('Ada Obi', { interview_score: 60, cv_score: 90 }),
    person('Chidi Okafor', { interview_score: 90, cv_score: 50 }),
    person('Bola Ade', { interview_score: 75, cv_score: null }),
  ]

  it('sorts the list by a score, highest first, with anyone without it last, keeping each number', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    fireEvent.change(screen.getByLabelText('Sort candidates by'), { target: { value: 'interview' } })
    expect(rowNames().map((t) => t.match(/Ada|Chidi|Bola/)[0])).toEqual(['Chidi', 'Bola', 'Ada'])

    fireEvent.change(screen.getByLabelText('Sort candidates by'), { target: { value: 'cv' } })
    expect(rowNames().map((t) => t.match(/Ada|Chidi|Bola/)[0])).toEqual(['Ada', 'Chidi', 'Bola'])
    // Bola was third on the list and still is called 3, however the list is sorted.
    expect(rowNames()[2]).toMatch(/^3/)
  })

  it('filters by status, with a count on each, and says nothing when there is one status only', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [THREE[0], ENDED_EARLY, PENDING] } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    fireEvent.click(screen.getByRole('button', { name: 'Ended early (1)' }))
    expect(rowNames()).toHaveLength(1)
    expect(rowNames()[0]).toMatch(/Bola Ade/)

    fireEvent.click(screen.getByRole('button', { name: 'All (3)' }))
    expect(rowNames()).toHaveLength(3)
  })

  it('shows no status filter when every candidate is in the same state', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    expect(screen.queryByRole('button', { name: /^All/ })).not.toBeInTheDocument()
  })

  it('searches by name once the list is long, and says when nobody matches', async () => {
    const many = Array.from({ length: 7 }, (_, i) => person(`Person ${i + 1}`))
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: many } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    fireEvent.change(screen.getByLabelText('Search candidates by name'), { target: { value: 'person 4' } })
    expect(rowNames()).toHaveLength(1)

    fireEvent.change(screen.getByLabelText('Search candidates by name'), { target: { value: 'nobody' } })
    expect(screen.getByText('No candidate matches this search.')).toBeInTheDocument()
  })

  it('has no search box on a short list', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    expect(screen.queryByLabelText('Search candidates by name')).not.toBeInTheDocument()
  })

  it('shows the suggested band on the row of a candidate with a complete weighted score', async () => {
    const report = {
      rows: [], bands: {}, key_flags: [], complete: true, score: 88, band: 'Strong shortlist', unassessed: [],
    }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [person('Ada Obi', { score_report: report })] } })
    renderPage()

    const row = within(await screen.findByRole('button', { name: /Ada Obi/ }))
    expect(row.getByText('Strong shortlist')).toBeInTheDocument()
  })

  it('flags a reviewed score with a small tag on the row and in the detail, and says nothing about who or why', async () => {
    const reviewed = person('Ada Obi', { interview_score: 89, interview_reviewed: true })
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [reviewed, person('Chidi Okafor')] } })
    renderPage()

    const row = within(await screen.findByRole('button', { name: /Ada Obi/ }))
    expect(row.getByTestId('reviewed-tag')).toBeInTheDocument()
    expect(within(screen.getByRole('button', { name: /Chidi Okafor/ })).queryByTestId('reviewed-tag')).not.toBeInTheDocument()
    const detail = within(await screen.findByRole('region', { name: 'Ada Obi, interview details' }))
    expect(detail.getAllByTestId('reviewed-tag').length).toBeGreaterThan(0)
    expect(screen.queryByText(/Elevare administrator|adjusted|changed by/i)).not.toBeInTheDocument()
  })

  it('flags a reviewed weighted score on its own tab and on the row', async () => {
    const report = {
      rows: [], bands: {}, key_flags: [], complete: true, score: 89, band: 'Strong shortlist', unassessed: [], reviewed: true,
    }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [person('Ada Obi', { score_report: report })] } })
    renderPage()

    const row = within(await screen.findByRole('button', { name: /Ada Obi/ }))
    expect(row.getByTestId('reviewed-tag')).toBeInTheDocument()
    expect(row.getByText('Strong shortlist')).toBeInTheDocument()
  })

  it('offers only the sorts there is something to sort by, which are the list order and the CV score when scores are off', async () => {
    const off = (name) => person(name, { interview_score: null, score_report: null })
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [off('Ada Obi'), off('Chidi Okafor')] } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    const options = within(screen.getByLabelText('Sort candidates by')).getAllByRole('option').map((o) => o.textContent)

    expect(options).toEqual(['Order on the list', 'CV score'])
  })

  it('offers every sort when the scores are there', async () => {
    const report = { rows: [], bands: {}, key_flags: [], complete: true, score: 88, band: 'Strong shortlist', unassessed: [] }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [person('Ada Obi', { score_report: report })] } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    const options = within(screen.getByLabelText('Sort candidates by')).getAllByRole('option').map((o) => o.textContent)

    expect(options).toEqual(['Order on the list', 'Interview score', 'Weighted score', 'CV score'])
  })

  it('shows a hidden-score candidate with no score chip, no band and no incomplete notice', async () => {
    const hidden = {
      rows: [{ name: 'Strategy', weight: 100, key: true, rating: 4 }],
      points: 0, assessed_weight: 100, total_weight: 100, complete: true, score: null, band: null, bands: {},
      key_min_rating: 3, key_flags: [], unassessed: [], hidden: true,
    }
    api.get.mockResolvedValueOnce({
      data: { ...RESULTS, candidates: [person('Ada Obi', { interview_score: null, score_report: hidden, cv_score: null })] },
    })
    renderPage()

    const row = within(await screen.findByRole('button', { name: /Ada Obi/ }))
    expect(row.queryByText(/Interview/)).toBeNull()
    expect(screen.queryByText(/Incomplete score/)).not.toBeInTheDocument()
    expect(screen.queryByTestId('weighted-band')).not.toBeInTheDocument()
  })

  it('gives the client a Scorecard tab laid out as the printed scorecard, named for the candidate', async () => {
    const scorecard = {
      rows: [{ name: 'Strategy', weight: 100, key: true, rating: 3.5, points: 35, evidence: 'Lagos mapping and a corridor pilot.' }],
      total_points: 35, max_points: 50, total_score: 70, practical_rating: null, strengths: ['Clear.'], decision: 'Proceed to Final Interview', panel_decision: null, hidden: false,
    }
    const record = { reference: 'EL-1', role: 'National Sales Manager', interview_date: null, duration_minutes: 10, interviewer: 'x', top_strengths: [], top_gaps: [], claims_to_verify: [], reference_check_questions: [], panel_decision: null }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [person('Ehi Okpepe', { scorecard, record })] } })
    renderPage()

    fireEvent.click(await screen.findByRole('tab', { name: 'Scorecard' }))

    const sheet = screen.getByRole('region', { name: 'Scorecard' })
    expect(within(sheet).getByRole('heading', { name: 'Interview Scorecard: National Sales Manager' })).toBeInTheDocument()
    expect(within(sheet).getByText(/Candidate Name:/).parentElement).toHaveTextContent('Candidate Name: Ehi Okpepe')
    expect(within(sheet).getByTestId('scorecard-total')).toHaveTextContent('35.0 / 50 (70/100)')
    expect(within(sheet).getByTestId('scorecard-decision')).toHaveTextContent('Proceed to Final Interview')
  })

  it('has no Scorecard tab for a candidate whose interview was not scored on competencies', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [person('Ada Obi', { scorecard: null })] } })
    renderPage()

    await screen.findByRole('tab', { name: 'Summary' })
    expect(screen.queryByRole('tab', { name: 'Scorecard' })).not.toBeInTheDocument()
  })

  it('shows no tag for a score nobody reviewed', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    await screen.findByRole('list', { name: 'Candidates' })

    expect(screen.queryByTestId('reviewed-tag')).not.toBeInTheDocument()
  })

  it('steps to the next and previous candidate in the list as it is shown, and stops at the ends', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    await screen.findByRole('region', { name: 'Ada Obi, interview details' })

    expect(screen.getByText('Candidate 1 of 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous candidate' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Next candidate' }))
    expect(screen.getByRole('region', { name: 'Chidi Okafor, interview details' })).toBeInTheDocument()
    expect(screen.getByText('Candidate 2 of 3')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Next candidate' }))
    expect(screen.getByText('Candidate 3 of 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next candidate' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Previous candidate' }))
    expect(screen.getByRole('region', { name: 'Chidi Okafor, interview details' })).toBeInTheDocument()
  })

  it('skips a candidate with nothing to open when stepping, and gives that row no button', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [THREE[0], PENDING, THREE[1]] } })
    renderPage()
    await screen.findByRole('region', { name: 'Ada Obi, interview details' })

    expect(screen.queryByRole('button', { name: /Candidate 2/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next candidate' }))
    expect(screen.getByRole('region', { name: 'Chidi Okafor, interview details' })).toBeInTheDocument()
    expect(screen.getByText('Candidate 2 of 2')).toBeInTheDocument()
  })

  it('opens the candidate named in the address', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage('/shared/interviews/tok123?c=3')

    expect(await screen.findByRole('region', { name: 'Bola Ade, interview details' })).toBeInTheDocument()
  })

  it('opens the first finished interview when the address names nobody who can be opened', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [PENDING, THREE[0]] } })
    renderPage('/shared/interviews/tok123?c=1')

    expect(await screen.findByRole('region', { name: 'Ada Obi, interview details' })).toBeInTheDocument()
  })

  it('says there is nothing to open yet when nobody has an interview or a CV assessment', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [PENDING] } })
    renderPage()

    expect(await screen.findByText(/There is nothing to open yet/)).toBeInTheDocument()
    expect(screen.getByText('Not interviewed yet')).toBeInTheDocument()
  })

  it('opens on the Summary tab for each candidate, and has no Scores or Record tab without them', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    await screen.findByRole('region', { name: 'Ada Obi, interview details' })

    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByRole('tab', { name: 'Scores' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Assessment record' })).not.toBeInTheDocument()

    openTab('Conversation')
    fireEvent.click(screen.getByRole('button', { name: 'Next candidate' }))
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveAttribute('aria-selected', 'true')
  })

  it('on a phone, hides the list while a candidate is open and brings it back', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: THREE } })
    renderPage()
    const list = await screen.findByRole('list', { name: 'Candidates' })
    // Before anyone is chosen the list is what a phone shows.
    expect(list.closest('div.hidden')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Chidi Okafor/ }))
    expect(list.closest('div.hidden')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Back to all candidates' }))
    expect(list.closest('div.hidden')).toBeNull()
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

    expect(await screen.findByText('What the interview was set to cover')).toBeInTheDocument()
    expect(screen.getByText('Probe distributor management.')).toBeInTheDocument()
  })

  it('makes the questions the AI asked obvious: a numbered list, then each one set apart in the conversation', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    renderPage()

    await screen.findByRole('tab', { name: 'Conversation' })
    openTab('Conversation')
    const heading = screen.getByText('Questions asked')
    const list = heading.closest('div').querySelector('ol')
    expect(within(list).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Tell me about managing distributors?',
      'What was the hardest part?',
    ])
    // In the conversation every AI turn is labelled and every answer is the candidate's.
    expect(screen.getAllByText('Interviewer')).toHaveLength(2)
    expect(screen.getAllByText('Candidate').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('I grew the network from twelve to forty.')).toBeInTheDocument()
  })

  it('shows the recording and tells the viewer to reload if it stops', async () => {
    api.get.mockResolvedValueOnce({ data: RESULTS })
    const { container } = renderPage()

    await screen.findByText(/Reload the page if it stops playing/)
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

    const row = within(await screen.findByRole('button', { name: /Ada Obi/ }))
    expect(row.getByText('Interview').parentElement).toHaveTextContent('Interview 82')
    expect(row.getByText('CV').parentElement).toHaveTextContent('CV 74')
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

    await screen.findByRole('tab', { name: 'Conversation' })
    openTab('Conversation')
    expect(screen.getByText('Just the words the recording contains.')).toBeInTheDocument()
    expect(screen.getByText(/no speaker labels/)).toBeInTheDocument()
    expect(screen.queryByText('Questions asked')).not.toBeInTheDocument()
  })

  it('opens the first finished interview, and another when its row is chosen', async () => {
    const second = { ...COMPLETED, name: 'Chidi Okafor', interview_score: 60, cv_summary: 'Second CV.' }
    api.get.mockResolvedValueOnce({ data: { ...RESULTS, candidates: [COMPLETED, second] } })
    renderPage()
    const detail = await screen.findByRole('region', { name: 'Ada Obi, interview details' })
    expect(within(detail).getByText('Strong sales background.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Chidi Okafor/ }))

    expect(screen.getByRole('region', { name: 'Chidi Okafor, interview details' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Ada Obi, interview details' })).not.toBeInTheDocument()
    expect(screen.getByText('Second CV.')).toBeInTheDocument()
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
    await screen.findByText('Regional Sales Manager')

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
