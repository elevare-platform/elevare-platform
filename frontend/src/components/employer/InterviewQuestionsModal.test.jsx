import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))

import api from '@/lib/api'
import InterviewQuestionsModal from './InterviewQuestionsModal'

const URL = '/api/v1/interviews/jobs/job-1/questions'
const CLOSING = { text: 'Before we finish, tell us what motivates you, your notice period, start date and pay.', time_limit_seconds: 90 }
const LIMITS = {
  max_questions: 40, // what the time allows, not a limit of its own
  default_questions: 5,
  max_total_seconds: 1200,
  closing_question: CLOSING,
  style: 'strict',
  follow_up_mode: 'STANDARD',
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

// The boxes with the questions' own text (each question also has a box for its probes).
const boxes = () => screen.getAllByLabelText(/^Question \d+/)
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

  it('still offers the closing question with a long list, since only time limits the count', async () => {
    api.get.mockResolvedValueOnce(
      loaded(Array.from({ length: 6 }, (_, i) => saved(i + 1, `Question number ${i + 1} about the job.`, 60)))
    )
    renderModal()

    expect(await screen.findByRole('button', { name: /Add the standard closing question/ })).toBeEnabled()
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
    expect(screen.getByText('2 questions')).toBeInTheDocument()
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

  it('lets the employer keep adding questions: there is no cap on how many, only on the total time', async () => {
    api.get.mockResolvedValueOnce(loaded(Array.from({ length: 6 }, (_, n) => saved(n + 1, `Question number ${n + 1} text here.`, 60))))
    renderModal()
    const add = await screen.findByRole('button', { name: /Add a question/ })

    fireEvent.click(add)
    fireEvent.click(add)

    expect(screen.getByText('8 questions')).toBeInTheDocument()
    expect(add).toBeEnabled()
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
        { text: 'First question to answer.', time_limit_seconds: 120, source: 'AI', competency: null, probes: null, follow_up_seconds: null, is_practical: false },
        { text: 'My own second question here.', time_limit_seconds: 90, source: 'EMPLOYER', competency: null, probes: null, follow_up_seconds: null, is_practical: false },
      ],
      follow_up_mode: 'STANDARD',
    })
    expect(onSaved).toHaveBeenCalled()
  })

  it('shows the server\'s refusal and stays open when saving fails', async () => {
    api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
    api.put.mockRejectedValueOnce({
      response: { status: 422, data: { code: 'VALIDATION_FAILED', message: 'x', details: [{ field: 'questions', message: 'Question 1 is too short to be a question.' }] } },
    })
    const { onClose } = renderModal()
    fireEvent.change(await screen.findByDisplayValue('First question to answer.'), { target: { value: 'First question, now edited.' } })

    fireEvent.click(saveButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('Question 1 is too short')
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
    expect(api.put).toHaveBeenCalledWith(URL, { questions: [], follow_up_mode: 'STANDARD' })
  })

  // --- the practical case ------------------------------------------------------------------

  describe('the practical case', () => {
    const practicalBox = (n) => screen.getByRole('checkbox', { name: `Mark question ${n} as the practical case` })

    it('lets the employer mark one question as the practical case and saves it', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.'), saved(2, 'Build a 90-day plan, stating assumptions.')]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      await screen.findByDisplayValue('First question to answer.')

      expect(practicalBox(1)).not.toBeChecked()
      fireEvent.click(practicalBox(2))
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions.map((x) => x.is_practical)).toEqual([false, true])
    })

    it('unticks the other question when another is ticked, so there is only ever one', async () => {
      api.get.mockResolvedValueOnce(loaded([{ ...saved(1, 'Build a 90-day plan, stating assumptions.'), is_practical: true }, saved(2, 'Second question to answer.')]))
      renderModal()
      await screen.findByDisplayValue('Second question to answer.')
      expect(practicalBox(1)).toBeChecked()

      fireEvent.click(practicalBox(2))

      expect(practicalBox(2)).toBeChecked()
      expect(practicalBox(1)).not.toBeChecked()
    })

    it('says what a practical case is, next to the box', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
      renderModal()

      expect(await screen.findByText(/scored on its own out of 5 and not part of the weighted score/)).toBeInTheDocument()
    })

    it('keeps the practical mark of a set loaded from a template', async () => {
      const TEMPLATES = [{ code: 'national_sales_manager', title: 'National Sales Manager', question_count: 2, total_seconds: 360 }]
      api.get.mockResolvedValueOnce({ data: { ...loaded().data, question_templates: TEMPLATES } })
      api.post.mockResolvedValueOnce({
        data: {
          ...LIMITS,
          question_templates: TEMPLATES,
          follow_up_mode: 'STANDARD',
          saved: true,
          questions: [saved(1, 'Tell me about a distributor network you built.', 120), { ...saved(2, 'Build a 90-day activation plan.', 240), is_practical: true }],
        },
      })
      renderModal()

      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'national_sales_manager' } })
      fireEvent.click(screen.getByRole('button', { name: 'Use this set' }))
      await screen.findByDisplayValue('Build a 90-day activation plan.')

      expect(practicalBox(1)).not.toBeChecked()
      expect(practicalBox(2)).toBeChecked()
    })
  })

  // --- the ready-made sets -----------------------------------------------------------------

  describe('the ready-made sets', () => {
    const TEMPLATES = [
      { code: 'national_sales_manager', title: 'National Sales Manager', question_count: 8, total_seconds: 1050 },
      { code: 'senior_marketing_manager', title: 'Senior Marketing Manager', question_count: 10, total_seconds: 1050 },
    ]
    const withTemplates = (questions = []) => ({ data: { ...loaded(questions).data, question_templates: TEMPLATES } })
    const appliedResponse = {
      data: {
        ...LIMITS,
        question_templates: TEMPLATES,
        follow_up_mode: 'STANDARD',
        questions: [
          { ...saved(1, 'You are preparing to launch Seasonings across Nigeria. How would you plan it?', 150), competency: 'Route-to-market', probes: 'Which markets would you prioritise?' },
          { ...saved(2, 'Tell me about a time you built a distributor network.', 120), competency: 'Route-to-market', probes: null },
        ],
      },
    }
    const useButton = () => screen.getByRole('button', { name: 'Use this set' })

    it('lists the roles with their question counts, and cannot be used until one is chosen', async () => {
      api.get.mockResolvedValueOnce(withTemplates())
      renderModal()

      const picker = await screen.findByLabelText('Start from a ready-made set')

      expect(within(picker).getAllByRole('option').map((o) => o.textContent)).toEqual([
        'Choose a role',
        'National Sales Manager (8 questions)',
        'Senior Marketing Manager (10 questions)',
      ])
      expect(useButton()).toBeDisabled()
      expect(screen.getByText(/word for word, with their optional probes/)).toBeInTheDocument()
    })

    it('is not shown when the server has none', async () => {
      api.get.mockResolvedValueOnce(loaded())
      renderModal()
      await screen.findByRole('button', { name: /Add a question/ })

      expect(screen.queryByLabelText('Start from a ready-made set')).not.toBeInTheDocument()
    })

    it('asks before replacing the current questions, and does nothing if the answer is no', async () => {
      api.get.mockResolvedValueOnce(withTemplates([saved(1, 'An existing question to keep?')]))
      confirmSpy.mockReturnValue(false)
      renderModal()

      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'national_sales_manager' } })
      fireEvent.click(useButton())

      expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Replace this job\'s questions and scoring profile with the National Sales Manager set'))
      expect(api.post).not.toHaveBeenCalled()
      expect(screen.getByDisplayValue('An existing question to keep?')).toBeInTheDocument()
    })

    it('loads and saves the role\'s set at once, shows it with its probes, and counts as saved', async () => {
      api.get.mockResolvedValueOnce(withTemplates([saved(1, 'An existing question to replace?')]))
      api.post.mockResolvedValueOnce(appliedResponse)
      const { onSaved } = renderModal()

      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'national_sales_manager' } })
      fireEvent.click(useButton())

      expect(await screen.findByDisplayValue(/You are preparing to launch Seasonings across Nigeria/)).toBeInTheDocument()
      expect(api.post).toHaveBeenCalledWith(`${URL}/from-template`, { code: 'national_sales_manager' })
      expect(screen.queryByDisplayValue('An existing question to replace?')).not.toBeInTheDocument()
      expect(screen.getByDisplayValue('Which markets would you prioritise?')).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent('Loaded the National Sales Manager set: 2 questions')
      expect(screen.getByRole('status')).toHaveTextContent('It is saved')
      expect(saveButton()).toBeDisabled() // nothing unsaved
      expect(onSaved).toHaveBeenCalled()
      expect(api.put).not.toHaveBeenCalled()
    })

    it('does not ask for confirmation to the same degree when there is nothing to replace', async () => {
      api.get.mockResolvedValueOnce(withTemplates())
      api.post.mockResolvedValueOnce(appliedResponse)
      renderModal()

      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'senior_marketing_manager' } })
      fireEvent.click(useButton())

      expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Start from the Senior Marketing Manager set?'))
      await screen.findByDisplayValue(/You are preparing to launch Seasonings across Nigeria/)
    })

    it('shows the server\'s refusal and keeps what was there when loading fails', async () => {
      api.get.mockResolvedValueOnce(withTemplates([saved(1, 'An existing question to keep?')]))
      api.post.mockRejectedValueOnce({ response: { status: 403, data: { message: 'You do not have access to this job' } } })
      renderModal()

      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'national_sales_manager' } })
      fireEvent.click(useButton())

      expect(await screen.findByRole('alert')).toHaveTextContent('You do not have access to this job')
      expect(screen.getByDisplayValue('An existing question to keep?')).toBeInTheDocument()
    })

    it('shows the set and keeps the time warning when its answer times are longer than the interview allows', async () => {
      const long = Array.from({ length: 8 }, (_, n) => ({
        ...saved(n + 1, `Colton question number ${n + 1} about the role.`, 150),
        competency: 'Route-to-market',
        probes: 'Which markets would you prioritise?',
      }))
      api.get.mockResolvedValueOnce(withTemplates())
      api.post.mockResolvedValueOnce({
        data: { ...LIMITS, max_total_seconds: 600, question_templates: TEMPLATES, follow_up_mode: 'STANDARD', saved: false, questions: long },
      })
      const { onSaved } = renderModal()

      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'national_sales_manager' } })
      fireEvent.click(useButton())

      // The questions are shown, not lost, ...
      expect(await screen.findByDisplayValue('Colton question number 1 about the role.')).toBeInTheDocument()
      expect(screen.getAllByLabelText('Time to answer')).toHaveLength(8)
      // ... the message about the time stays, with the reason Save is off ...
      const problems = screen.getByRole('list', { name: 'Problems with the list' })
      expect(within(problems).getByText(/add up to 20 min, but the whole interview is limited to 10 min/)).toBeInTheDocument()
      expect(screen.getByTestId('cannot-save-note')).toHaveTextContent('Shorten the answer times to save.')
      expect(screen.getByRole('status')).toHaveTextContent('not saved yet')
      expect(saveButton()).toBeDisabled()
      expect(onSaved).not.toHaveBeenCalled()
      expect(api.put).not.toHaveBeenCalled()

      // ... and shortening the times is what lets it be saved.
      for (const select of screen.getAllByLabelText('Time to answer')) {
        fireEvent.change(select, { target: { value: '60' } })
      }
      expect(screen.queryByRole('list', { name: 'Problems with the list' })).not.toBeInTheDocument()
      expect(screen.queryByTestId('cannot-save-note')).not.toBeInTheDocument()
      expect(saveButton()).toBeEnabled()
    })

    it('can still be edited and saved after a set is loaded, with the tags it came with', async () => {
      api.get.mockResolvedValueOnce(withTemplates())
      api.post.mockResolvedValueOnce({ data: { ...appliedResponse.data, competencies: ['Route-to-market'] } })
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      fireEvent.change(await screen.findByLabelText('Start from a ready-made set'), { target: { value: 'national_sales_manager' } })
      fireEvent.click(useButton())
      await screen.findByDisplayValue(/You are preparing to launch Seasonings across Nigeria/)

      fireEvent.change(screen.getAllByLabelText('Time to answer')[0], { target: { value: '240' } })
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      const sent = api.put.mock.calls[0][1]
      expect(sent.questions.map((x) => [x.competency, x.time_limit_seconds, x.probes])).toEqual([
        ['Route-to-market', 240, 'Which markets would you prioritise?'],
        ['Route-to-market', 120, null],
      ])
      expect(sent.follow_up_mode).toBe('STANDARD')
    })
  })

  // --- what the AI does after an answer --------------------------------------------------

  describe('the follow-up choice and the probes', () => {
    const modeRadio = (name) => screen.getByRole('radio', { name: new RegExp(name) })

    it('shows the job\'s saved choice, and offers the three options', async () => {
      api.get.mockResolvedValueOnce({ data: { ...loaded([saved(1, 'First question to answer.')]).data, follow_up_mode: 'PROBES_ONLY' } })
      renderModal()
      await screen.findByDisplayValue('First question to answer.')

      expect(screen.getAllByRole('radio')).toHaveLength(3)
      expect(modeRadio('Only my probes')).toBeChecked()
      expect(modeRadio('Follow up when needed')).not.toBeChecked()
      expect(modeRadio('Questions only')).not.toBeChecked()
    })

    it('starts on "Follow up when needed" for a job that never chose', async () => {
      api.get.mockResolvedValueOnce({ data: { ...loaded([saved(1, 'First question to answer.')]).data, follow_up_mode: undefined } })
      renderModal()
      await screen.findByDisplayValue('First question to answer.')

      expect(modeRadio('Follow up when needed')).toBeChecked()
    })

    it('saves the chosen option with the list', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      await screen.findByDisplayValue('First question to answer.')

      fireEvent.click(modeRadio('Questions only'))
      expect(saveButton()).toBeEnabled() // changing only the choice is a change
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].follow_up_mode).toBe('NONE')
    })

    it('gives each question a box for its own probes, one per line, and saves them', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.'), { ...saved(2, 'Second question to answer.'), probes: 'What was your part?' }]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      const probeBoxes = await screen.findAllByLabelText(/follow-up probes/)

      expect(probeBoxes).toHaveLength(2)
      expect(probeBoxes[1]).toHaveValue('What was your part?')
      fireEvent.change(probeBoxes[0], { target: { value: 'How big was it?\nWhat did it deliver?' } })
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions.map((x) => x.probes)).toEqual([
        'How big was it?\nWhat did it deliver?',
        'What was your part?',
      ])
    })

    it('keeps an AI draft marked as the AI\'s when probes are added to it', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.', 120, 'AI')]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()

      fireEvent.change(await screen.findByLabelText(/follow-up probes/), { target: { value: 'How big was it?' } })
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions[0].source).toBe('AI')
    })

    it('hides the probe boxes for "Questions only", and says what "Only my probes" needs', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
      renderModal()
      await screen.findByDisplayValue('First question to answer.')

      fireEvent.click(modeRadio('Questions only'))
      expect(screen.queryByLabelText(/follow-up probes/)).not.toBeInTheDocument()

      fireEvent.click(modeRadio('Only my probes'))
      expect(screen.getByLabelText('Follow-up probes the AI may ask (one per line)')).toBeInTheDocument()
      expect(screen.getByTestId('no-probes-note')).toHaveTextContent('the AI will not ask any follow-up')

      fireEvent.change(screen.getByLabelText(/follow-up probes/i), { target: { value: 'What was your part?' } })
      expect(screen.queryByTestId('no-probes-note')).not.toBeInTheDocument()
    })

    it('gives the follow-up its own time under the probes, 1 min 30 s unless set, and saves what is chosen', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.'), { ...saved(2, 'Second question to answer.'), follow_up_seconds: 180 }]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      const times = await screen.findAllByLabelText('Time to answer a follow-up')

      expect(times[0]).toHaveValue('90') // none set: the platform's 1 min 30 s
      expect(times[1]).toHaveValue('180')
      expect(within(times[0]).getAllByRole('option').map((o) => o.textContent)).toEqual([
        '30 s', '1 min', '1 min 30 s', '2 min', '2 min 30 s', '3 min', '3 min 30 s', '4 min', '4 min 30 s', '5 min',
      ])
      fireEvent.change(times[0], { target: { value: '120' } })
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions.map((x) => x.follow_up_seconds)).toEqual([120, 180])
    })

    it('saves no follow-up time for a question where none was chosen, so the default applies', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
      api.put.mockResolvedValueOnce({ data: { ...LIMITS, questions: [] } })
      renderModal()
      await screen.findByLabelText('Time to answer a follow-up')

      fireEvent.click(modeRadio('Only my probes'))
      fireEvent.click(saveButton())

      await waitFor(() => expect(api.put).toHaveBeenCalled())
      expect(api.put.mock.calls[0][1].questions[0].follow_up_seconds).toBeNull()
    })

    it('hides the follow-up time for "Questions only"', async () => {
      api.get.mockResolvedValueOnce({ data: { ...loaded([saved(1, 'First question to answer.')]).data, follow_up_mode: 'NONE' } })
      renderModal()
      await screen.findByDisplayValue('First question to answer.')

      expect(screen.queryByLabelText('Time to answer a follow-up')).not.toBeInTheDocument()
    })

    it('warns that few follow-ups will fit when the answer times use nearly all the interview', async () => {
      api.get.mockResolvedValueOnce(loaded(Array.from({ length: 8 }, (_, n) => saved(n + 1, `Question number ${n + 1} about the job.`, 140))))
      renderModal()

      const note = await screen.findByTestId('little-time-for-follow-ups')

      expect(note).toHaveTextContent('Only 1 min 20 s of the 20 min is left')
      expect(note).toHaveTextContent('few or none will be asked')
    })

    it('does not warn when there is room, when follow-ups are off, or when the list is over the limit', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.', 120)]))
      const { unmount } = render(<InterviewQuestionsModal jobId="job-1" hasBrief onClose={vi.fn()} />)
      await screen.findByLabelText('Time to answer a follow-up')
      expect(screen.queryByTestId('little-time-for-follow-ups')).not.toBeInTheDocument()
      unmount()

      const full = Array.from({ length: 8 }, (_, n) => saved(n + 1, `Question number ${n + 1} about the job.`, 140))
      api.get.mockResolvedValueOnce({ data: { ...loaded(full).data, follow_up_mode: 'NONE' } })
      const second = render(<InterviewQuestionsModal jobId="job-1" hasBrief onClose={vi.fn()} />)
      await screen.findByDisplayValue('Question number 1 about the job.')
      expect(screen.queryByTestId('little-time-for-follow-ups')).not.toBeInTheDocument()
      second.unmount()

      const over = Array.from({ length: 9 }, (_, n) => saved(n + 1, `Question number ${n + 1} about the job.`, 150))
      api.get.mockResolvedValueOnce(loaded(over))
      render(<InterviewQuestionsModal jobId="job-1" hasBrief onClose={vi.fn()} />)
      await screen.findByDisplayValue('Question number 1 about the job.')
      expect(screen.queryByTestId('little-time-for-follow-ups')).not.toBeInTheDocument() // the red limit message says it
      expect(screen.getByRole('list', { name: 'Problems with the list' })).toBeInTheDocument()
    })

    it('refuses too many or too long probes before saving', async () => {
      api.get.mockResolvedValueOnce(loaded([saved(1, 'First question to answer.')]))
      renderModal()
      const box = await screen.findByLabelText(/follow-up probes/)

      fireEvent.change(box, { target: { value: Array.from({ length: 7 }, (_, n) => `Probe ${n}?`).join('\n') } })
      expect(screen.getByText('Question 1 has too many probes. Keep it to 6.')).toBeInTheDocument()
      expect(saveButton()).toBeDisabled()

      fireEvent.change(box, { target: { value: 'x'.repeat(301) } })
      expect(screen.getByText(/A probe on question 1 is too long/)).toBeInTheDocument()
    })
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
