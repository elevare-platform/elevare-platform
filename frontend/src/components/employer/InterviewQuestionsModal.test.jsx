import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))

import api from '@/lib/api'
import InterviewQuestionsModal from './InterviewQuestionsModal'

const URL = '/api/v1/interviews/jobs/job-1/questions'
const CLOSING = { text: 'Before we finish, tell us what motivates you, your notice period, start date and pay.', time_limit_seconds: 90 }
const LIMITS = {
  max_questions: 6,
  default_questions: 5,
  max_total_seconds: 1200,
  closing_question: CLOSING,
  style: 'strict',
}

const saved = (position, text, seconds = 120, source = 'EMPLOYER') => ({
  id: `id-${position}`,
  position,
  text,
  time_limit_seconds: seconds,
  source,
})

function loaded(questions = []) {
  return {
    data: { ...LIMITS, questions, total_seconds: questions.reduce((s, x) => s + x.time_limit_seconds, 0) },
  }
}

function renderModal(props = {}) {
  const onClose = vi.fn()
  const onSaved = vi.fn()
  render(<InterviewQuestionsModal jobId="job-1" hasBrief onClose={onClose} onSaved={onSaved} {...props} />)
  return { onClose, onSaved }
}

const boxes = () => screen.getAllByRole('textbox')
const saveButton = () => screen.getByRole('button', { name: 'Save questions' })

describe('InterviewQuestionsModal', () => {
  let confirmSpy

  beforeEach(() => {
    vi.clearAllMocks()
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => confirmSpy.mockRestore())

  describe('with a scoring profile', () => {
    const WITH_PROFILE = { competencies: ['Strategy', 'P&L'] }

    function loadedWithProfile(questions) {
      return { data: { ...loaded(questions).data, ...WITH_PROFILE, untested_competencies: [] } }
    }

    it('offers each question a competency to test, and none when the job has no profile', async () => {
      api.get.mockResolvedValueOnce(loadedWithProfile([saved(1, 'How do you set a strategy for launches?', 120)]))
      const { unmount } = render(<InterviewQuestionsModal jobId="job-1" hasBrief onClose={vi.fn()} onSaved={vi.fn()} />)

      const select = await screen.findByLabelText('Tests competency')
      expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['Not tagged', 'Strategy', 'P&L'])
      unmount()

      api.get.mockResolvedValueOnce(loaded([saved(1, 'How do you set a strategy for launches?', 120)]))
      renderModal()
      await screen.findByLabelText('Time to answer')
      expect(screen.queryByLabelText('Tests competency')).not.toBeInTheDocument()
    })

    it('shows a saved tag, warns about the competencies no question tests, and updates the warning as tags change', async () => {
      api.get.mockResolvedValueOnce(
        loadedWithProfile([{ ...saved(1, 'How do you set a strategy for launches?', 120), competency: 'Strategy' }])
      )
      renderModal()

      expect(await screen.findByLabelText('Tests competency')).toHaveValue('Strategy')
      expect(screen.getByTestId('untested-competencies')).toHaveTextContent('No question is tagged with: P&L.')

      fireEvent.change(screen.getByLabelText('Tests competency'), { target: { value: 'P&L' } })
      expect(screen.getByTestId('untested-competencies')).toHaveTextContent('No question is tagged with: Strategy.')

      fireEvent.change(screen.getByLabelText('Tests competency'), { target: { value: '' } })
      expect(screen.getByTestId('untested-competencies')).toHaveTextContent('No question is tagged with: Strategy, P&L.')
    })

    it('has no warning when every competency has a question', async () => {
      api.get.mockResolvedValueOnce(
        loadedWithProfile([
          { ...saved(1, 'How do you set a strategy for launches?', 120), competency: 'Strategy' },
          { ...saved(2, 'How do you manage the P and L of a unit?', 120), competency: 'P&L' },
        ])
      )
      renderModal()

      await screen.findAllByLabelText('Tests competency')
      expect(screen.queryByTestId('untested-competencies')).not.toBeInTheDocument()
    })

    it('saves the tag with the question, and null when it has none', async () => {
      api.get.mockResolvedValueOnce(loadedWithProfile([saved(1, 'How do you set a strategy for launches?', 120), saved(2, 'Tell me about a time you led a team.', 90)]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      const selects = await screen.findAllByLabelText('Tests competency')

      fireEvent.change(selects[0], { target: { value: 'Strategy' } })
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions.map((q) => q.competency)).toEqual(['Strategy', null])
    })

    it('does not turn an AI draft into the employer\'s own wording by tagging it', async () => {
      api.get.mockResolvedValueOnce(loadedWithProfile([saved(1, 'How do you set a strategy for launches?', 120, 'AI')]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()

      fireEvent.change(await screen.findByLabelText('Tests competency'), { target: { value: 'Strategy' } })
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions[0].source).toBe('AI')
    })
  })

  it('adds the standard closing question with its own text and time, and offers it only once', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'Describe a system you designed.', 180)]))
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /Add the standard closing question/ }))

    expect(boxes()[1]).toHaveValue(CLOSING.text)
    expect(screen.getByRole('button', { name: /Add the standard closing question/ })).toBeDisabled()
  })

  it('does not offer the closing question again when the list already has it, even edited slightly in spacing', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'Describe a system.', 120), saved(2, `  ${CLOSING.text}  `, 90)]))
    renderModal()

    expect(await screen.findByRole('button', { name: /Add the standard closing question/ })).toBeDisabled()
  })

  it('offers the closing question again once it has been removed or reworded', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'Describe a system.', 120), saved(2, 'Anything else to add?', 90)]))
    renderModal()

    expect(await screen.findByRole('button', { name: /Add the standard closing question/ })).toBeEnabled()
  })

  it('does not offer the closing question when the list is full', async () => {
    api.get.mockResolvedValueOnce(
      loaded(Array.from({ length: 6 }, (_, i) => saved(i + 1, `Question number ${i + 1} about the job.`, 60)))
    )
    renderModal()

    expect(await screen.findByRole('button', { name: /Add the standard closing question/ })).toBeDisabled()
  })

  it('works with a server that does not send a closing question', async () => {
    api.get.mockResolvedValueOnce({ data: { ...LIMITS, closing_question: undefined, questions: [], total_seconds: 0 } })
    renderModal()

    await screen.findByRole('button', { name: /Add a question/ })
    expect(screen.queryByRole('button', { name: /Add the standard closing question/ })).not.toBeInTheDocument()
  })

  it('loads the job\'s saved questions, in order, with their times and the limits', async () => {
    api.get.mockResolvedValueOnce(
      loaded([saved(1, 'Describe a system you designed.', 180), saved(2, 'How do you test a risky change?', 90, 'AI')])
    )
    renderModal()

    expect(await screen.findByDisplayValue('Describe a system you designed.')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith(URL)
    expect(screen.getByDisplayValue('How do you test a risky change?')).toBeInTheDocument()
    expect(screen.getByText('AI draft')).toBeInTheDocument()
    expect(screen.getByText('2 of 6 questions')).toBeInTheDocument()
    expect(screen.getByText(/Answer time: 4 min 30 s of 20 min/)).toBeInTheDocument()
  })

  it('says so, and does not pretend, when the questions cannot be loaded', async () => {
    api.get.mockRejectedValueOnce(new Error('network'))
    renderModal()

    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
    expect(saveButton()).toBeDisabled()
  })

  it('shows an empty state and nothing to save when there are no questions', async () => {
    api.get.mockResolvedValueOnce(loaded())
    renderModal()

    expect(await screen.findByText(/No questions yet/)).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  // --- drafting -------------------------------------------------------------------------

  it('cannot draft without an interview brief, and says why', async () => {
    api.get.mockResolvedValueOnce(loaded())
    renderModal({ hasBrief: false })

    const draft = await screen.findByRole('button', { name: /Draft from the interview brief/ })

    expect(draft).toBeDisabled()
    expect(screen.getByText(/Write the interview brief first/)).toBeInTheDocument()
  })

  it('shows a draft marked as the AI\'s, does not save it, and lets the employer save it after reading', async () => {
    api.get.mockResolvedValueOnce(loaded())
    api.post.mockResolvedValueOnce({
      data: {
        ...LIMITS,
        total_seconds: 210,
        questions: [
          { text: 'Describe a system you designed and why.', time_limit_seconds: 90, source: 'AI' },
          { text: 'How do you test a risky change?', time_limit_seconds: 120, source: 'AI' },
        ],
      },
    })
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /Draft from the interview brief/ }))

    expect(await screen.findByDisplayValue('Describe a system you designed and why.')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith(`${URL}/draft`, {})
    expect(api.put).not.toHaveBeenCalled() // a draft is never saved on its own
    expect(screen.getByRole('status')).toHaveTextContent('Drafted 2 questions')
    expect(screen.getAllByText('AI draft')).toHaveLength(2)
    expect(saveButton()).toBeEnabled()
  })

  it('asks before throwing away the questions already there', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'An existing question to keep?')]))
    confirmSpy.mockReturnValue(false)
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /Draft from the interview brief/ }))

    expect(confirmSpy).toHaveBeenCalledWith('Replace your current questions with a new draft?')
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getByDisplayValue('An existing question to keep?')).toBeInTheDocument()
  })

  it('shows the server\'s own message when drafting fails, and keeps what was there', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'An existing question to keep?')]))
    api.post.mockRejectedValueOnce({
      response: { status: 503, data: { code: 'INTERVIEW_QUESTIONS_DRAFT_FAILED', message: 'We could not draft the questions just now. Please try again, or write them yourself.' } },
    })
    renderModal()

    fireEvent.click(await screen.findByRole('button', { name: /Draft from the interview brief/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('write them yourself')
    expect(screen.getByDisplayValue('An existing question to keep?')).toBeInTheDocument()
  })

  // --- editing --------------------------------------------------------------------------

  it('lets the employer add a question up to the limit, and then stops', async () => {
    api.get.mockResolvedValueOnce(loaded(Array.from({ length: 5 }, (_, n) => saved(n + 1, `Question number ${n + 1} text here.`))))
    renderModal()
    const add = await screen.findByRole('button', { name: /Add a question/ })

    fireEvent.click(add)

    expect(screen.getByText('6 of 6 questions')).toBeInTheDocument()
    expect(add).toBeDisabled()
  })

  it('marks a drafted question as the employer\'s once they change it', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'Describe a system you designed.', 120, 'AI')]))
    renderModal()
    const box = await screen.findByDisplayValue('Describe a system you designed.')

    fireEvent.change(box, { target: { value: 'Describe the best system you designed.' } })

    expect(screen.queryByText('AI draft')).not.toBeInTheDocument()
  })

  it('moves and removes questions', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.'), saved(2, 'Second question to answer.'), saved(3, 'Third question to answer.')]))
    renderModal()
    await screen.findByDisplayValue('First question to answer.')

    fireEvent.click(screen.getByRole('button', { name: 'Move question 2 up' }))
    expect(boxes().map((b) => b.value)).toEqual(['Second question to answer.', 'First question to answer.', 'Third question to answer.'])

    fireEvent.click(screen.getByRole('button', { name: 'Remove question 1' }))
    expect(boxes().map((b) => b.value)).toEqual(['First question to answer.', 'Third question to answer.'])
  })

  it('cannot move the first question up or the last one down', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.'), saved(2, 'Second question to answer.')]))
    renderModal()
    await screen.findByDisplayValue('First question to answer.')

    expect(screen.getByRole('button', { name: 'Move question 1 up' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move question 2 down' })).toBeDisabled()
  })

  it('changes the time to answer and keeps the total up to date', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.', 120)]))
    renderModal()
    const select = await screen.findByLabelText('Time to answer')

    fireEvent.change(select, { target: { value: '300' } })

    expect(select).toHaveValue('300')
    expect(screen.getByText(/Answer time: 5 min of 20 min/)).toBeInTheDocument()
  })

  it('says what is wrong, and will not save, when the list breaks a rule', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'Why?'), saved(2, 'A long enough question here.', 600), saved(3, 'Another long enough question.', 600), saved(4, 'A third long enough question.', 600)]))
    renderModal()
    await screen.findByDisplayValue('Why?')
    fireEvent.change(boxes()[0], { target: { value: 'Why?!' } })

    const problems = screen.getByRole('list', { name: 'Problems with the list' })

    expect(within(problems).getByText('Question 1 is too short to be a question.')).toBeInTheDocument()
    expect(within(problems).getByText(/add up to 32 min, but the whole interview is limited to 20 min/)).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  // --- saving ---------------------------------------------------------------------------

  it('saves the list in order, with the times and who wrote each, then closes', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.', 120, 'AI')]))
    api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
    const { onClose, onSaved } = renderModal()
    await screen.findByDisplayValue('First question to answer.')
    fireEvent.click(screen.getByRole('button', { name: /Add a question/ }))
    fireEvent.change(boxes()[1], { target: { value: 'My own second question here.' } })
    fireEvent.change(screen.getAllByLabelText('Time to answer')[1], { target: { value: '90' } })

    fireEvent.click(saveButton())

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.put).toHaveBeenCalledWith(URL, {
      questions: [
        { text: 'First question to answer.', time_limit_seconds: 120, source: 'AI', competency: null },
        { text: 'My own second question here.', time_limit_seconds: 90, source: 'EMPLOYER', competency: null },
      ],
    })
    expect(onSaved).toHaveBeenCalled()
  })

  it('shows the server\'s refusal and stays open when saving fails', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
    api.put.mockRejectedValueOnce({
      response: { status: 422, data: { code: 'VALIDATION_FAILED', message: 'x', details: [{ field: 'questions', message: 'An interview can have at most 6 questions.' }] } },
    })
    const { onClose } = renderModal()
    fireEvent.change(await screen.findByDisplayValue('First question to answer.'), { target: { value: 'First question, now edited.' } })

    fireEvent.click(saveButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('at most 6 questions')
    expect(onClose).not.toHaveBeenCalled()
  })

  it('can clear the list by removing every question and saving', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'The only question to remove?')]))
    api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
    const { onClose } = renderModal()
    await screen.findByDisplayValue('The only question to remove?')

    fireEvent.click(screen.getByRole('button', { name: 'Remove question 1' }))
    fireEvent.click(saveButton())

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.put).toHaveBeenCalledWith(URL, { questions: [] })
  })

  // --- closing --------------------------------------------------------------------------

  it('closes at once when nothing was changed', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
    const { onClose } = renderModal()
    await screen.findByDisplayValue('First question to answer.')

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('asks before throwing away unsaved changes', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
    confirmSpy.mockReturnValue(false)
    const { onClose } = renderModal()
    fireEvent.change(await screen.findByDisplayValue('First question to answer.'), { target: { value: 'First question, edited.' } })

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    expect(confirmSpy).toHaveBeenCalledWith('You have unsaved changes. Close without saving?')
    expect(onClose).not.toHaveBeenCalled()
  })
})
