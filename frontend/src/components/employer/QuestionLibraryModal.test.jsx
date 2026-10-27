import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))

import api from '@/lib/api'
import QuestionLibraryModal from './QuestionLibraryModal'

const LIBRARY = '/api/v1/interviews/question-templates'

const question = (text, extra = {}) => ({ text, time_limit_seconds: 120, is_practical: false, ...extra })

const BUILT_IN = {
  id: 'national_sales_manager',
  kind: 'BUILT_IN',
  name: 'National Sales Manager',
  question_count: 2,
  total_seconds: 360,
  has_practical: true,
  has_scoring_profile: true,
  can_edit: false,
  questions: [question('Tell me about a distributor network you built.'), question('Build a 90-day activation plan.', { time_limit_seconds: 240, is_practical: true })],
}
const MINE = {
  id: 't-1',
  kind: 'COMPANY',
  name: 'Our sales set',
  question_count: 1,
  total_seconds: 120,
  has_practical: false,
  has_scoring_profile: false,
  created_by_name: 'Ada Obi',
  created_at: '2026-10-01T09:00:00Z',
  can_edit: true,
  questions: [question('Why do you want this role?')],
}
const THEIRS = { ...MINE, id: 't-2', name: 'Finance set', created_by_name: 'Tolu Bello', can_edit: false, questions: [question('Walk me through a month-end close.')] }
const OTHER_JOB = { job_id: 'job-9', title: 'Regional Manager', question_count: 3, total_seconds: 400, has_practical: false }

let reply
const answer = (overrides = {}) => {
  reply = { library: { built_in: [BUILT_IN], company: [MINE, THEIRS], can_save: true }, jobs: { items: [OTHER_JOB] }, ...overrides }
}

function renderLibrary(props = {}) {
  const onClose = vi.fn()
  const onApplied = vi.fn()
  render(<QuestionLibraryModal jobId="job-1" hasQuestions={false} onApplied={onApplied} onClose={onClose} {...props} />)
  return { onClose, onApplied }
}

const cards = () => screen.getAllByTestId('library-card')
const tab = (name) => screen.getByRole('tab', { name: new RegExp(name) })

describe('QuestionLibraryModal', () => {
  let confirmSpy

  beforeEach(() => {
    vi.resetAllMocks()
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    answer()
    api.get.mockImplementation((url, config) => {
      if (url === LIBRARY) return Promise.resolve({ data: reply.library, config })
      if (url === `${LIBRARY}/jobs`) return Promise.resolve({ data: reply.jobs })
      if (url === '/api/v1/interviews/jobs/job-9/questions') return Promise.resolve({ data: { questions: [question('Where is your region weakest?')] } })
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
  })
  afterEach(() => confirmSpy.mockRestore())

  it('opens on the Colton Group sets, with what each set holds', async () => {
    renderLibrary()

    const card = (await screen.findAllByTestId('library-card'))[0]
    expect(within(card).getByText('National Sales Manager')).toBeInTheDocument()
    expect(card).toHaveTextContent('2 questions · 6 min · practical case · scoring profile')
    expect(tab('Colton Group sets')).toHaveAttribute('aria-selected', 'true')
  })

  it('shows the company\'s sets with who saved them, and lets only the owner of a set rename or delete it', async () => {
    renderLibrary()
    await screen.findAllByTestId('library-card')

    fireEvent.click(tab("My company's sets"))

    const [mine, theirs] = cards()
    expect(mine).toHaveTextContent('Saved by Ada Obi on 1 Oct 2026')
    expect(within(mine).getByRole('button', { name: 'Rename Our sales set' })).toBeInTheDocument()
    expect(within(mine).getByRole('button', { name: 'Delete Our sales set' })).toBeInTheDocument()
    expect(theirs).toHaveTextContent('Saved by Tolu Bello')
    expect(within(theirs).queryByRole('button', { name: /Rename|Delete/ })).not.toBeInTheDocument()
    expect(within(theirs).getByRole('button', { name: 'Use this set' })).toBeInTheDocument()
  })

  it('searches after the typing settles, and asks the server for the matches', async () => {
    renderLibrary()
    await screen.findAllByTestId('library-card')
    api.get.mockClear()

    fireEvent.change(screen.getByTestId('library-search'), { target: { value: '  artwork  ' } })
    expect(api.get).not.toHaveBeenCalled() // not on every key

    await waitFor(() => expect(api.get).toHaveBeenCalledWith(LIBRARY, { params: { q: 'artwork' } }))
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('says so when nothing matches, in words for the tab', async () => {
    answer({ library: { built_in: [], company: [], can_save: true } })
    renderLibrary()
    expect(await screen.findByTestId('library-empty')).toHaveTextContent('No Colton Group set matches your search.')

    fireEvent.click(tab("My company's sets"))
    expect(screen.getByTestId('library-empty')).toHaveTextContent('Your company has not saved a set yet')
    expect(screen.getByTestId('library-empty')).toHaveTextContent('Save as template')
  })

  it('previews the questions of a set and hides them again', async () => {
    renderLibrary()
    const card = (await screen.findAllByTestId('library-card'))[0]

    fireEvent.click(within(card).getByRole('button', { name: 'Preview' }))

    const preview = within(card).getByTestId('library-preview')
    expect(preview).toHaveTextContent('Tell me about a distributor network you built.')
    expect(preview).toHaveTextContent('Practical case')
    fireEvent.click(within(card).getByRole('button', { name: 'Hide' }))
    expect(within(card).queryByTestId('library-preview')).not.toBeInTheDocument()
  })

  describe('the company\'s other jobs', () => {
    it('lists them for this job to copy from, leaving this job out', async () => {
      renderLibrary()
      await screen.findAllByTestId('library-card')

      fireEvent.click(tab('My other jobs'))

      expect(await screen.findByText('Regional Manager')).toBeInTheDocument()
      expect(api.get).toHaveBeenCalledWith(`${LIBRARY}/jobs`, { params: { exclude_job_id: 'job-1' } })
    })

    it('loads a job\'s questions only when it is previewed', async () => {
      renderLibrary()
      await screen.findAllByTestId('library-card')
      fireEvent.click(tab('My other jobs'))
      const card = (await screen.findAllByTestId('library-card'))[0]
      expect(api.get).not.toHaveBeenCalledWith('/api/v1/interviews/jobs/job-9/questions')

      fireEvent.click(within(card).getByRole('button', { name: 'Preview' }))

      expect(await within(card).findByTestId('library-preview')).toHaveTextContent('Where is your region weakest?')
    })

    it('says so when no other job has questions', async () => {
      answer({ jobs: { items: [] } })
      renderLibrary()
      await screen.findAllByTestId('library-card')

      fireEvent.click(tab('My other jobs'))

      expect(await screen.findByTestId('library-empty')).toHaveTextContent('other jobs have interview questions yet')
    })
  })

  describe('using a set', () => {
    it('starts a job with no questions from a Colton set after asking, and hands back the reply', async () => {
      const { onApplied } = renderLibrary()
      api.post.mockResolvedValueOnce({ data: { saved: true, questions: [question('From the set.')] } })
      const card = (await screen.findAllByTestId('library-card'))[0]

      fireEvent.click(within(card).getByRole('button', { name: 'Use this set' }))

      await waitFor(() => expect(onApplied).toHaveBeenCalledWith({ saved: true, questions: [question('From the set.')] }, 'National Sales Manager'))
      expect(confirmSpy).toHaveBeenCalledWith('Start from "National Sales Manager"? It also sets the job\'s scoring profile.')
      expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/jobs/job-1/questions/from-template', { code: 'national_sales_manager' })
    })

    it('warns that existing questions and the profile will be replaced', async () => {
      renderLibrary({ hasQuestions: true })
      api.post.mockResolvedValueOnce({ data: { questions: [] } })
      const card = (await screen.findAllByTestId('library-card'))[0]

      fireEvent.click(within(card).getByRole('button', { name: 'Use this set' }))

      await waitFor(() => expect(api.post).toHaveBeenCalled())
      expect(confirmSpy).toHaveBeenCalledWith('Replace this job\'s questions and scoring profile with "National Sales Manager"? Interviews already started keep the questions they began with.')
    })

    it('does nothing when the employer declines', async () => {
      const { onApplied } = renderLibrary({ hasQuestions: true })
      confirmSpy.mockReturnValue(false)
      const card = (await screen.findAllByTestId('library-card'))[0]

      fireEvent.click(within(card).getByRole('button', { name: 'Use this set' }))

      expect(api.post).not.toHaveBeenCalled()
      expect(onApplied).not.toHaveBeenCalled()
    })

    it('uses a company set by its id', async () => {
      const { onApplied } = renderLibrary()
      api.post.mockResolvedValueOnce({ data: { questions: [] } })
      await screen.findAllByTestId('library-card')
      fireEvent.click(tab("My company's sets"))

      fireEvent.click(within(cards()[1]).getByRole('button', { name: 'Use this set' }))

      await waitFor(() => expect(onApplied).toHaveBeenCalled())
      expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/jobs/job-1/questions/from-saved-template', { template_id: 't-2' })
      expect(onApplied.mock.calls[0][1]).toBe('Finance set')
    })

    it('copies from another job by its id, without a scoring profile in the warning', async () => {
      const { onApplied } = renderLibrary({ hasQuestions: true })
      api.post.mockResolvedValueOnce({ data: { questions: [] } })
      await screen.findAllByTestId('library-card')
      fireEvent.click(tab('My other jobs'))
      const card = (await screen.findAllByTestId('library-card'))[0]

      fireEvent.click(within(card).getByRole('button', { name: 'Use this set' }))

      await waitFor(() => expect(onApplied).toHaveBeenCalled())
      expect(api.post).toHaveBeenCalledWith('/api/v1/interviews/jobs/job-1/questions/from-job', { source_job_id: 'job-9' })
      expect(confirmSpy).toHaveBeenCalledWith('Replace this job\'s questions with "Regional Manager"? Interviews already started keep the questions they began with.')
    })

    it('shows the server\'s words and stays open when the set cannot be used', async () => {
      const { onApplied, onClose } = renderLibrary()
      api.post.mockRejectedValueOnce({ response: { status: 404, data: { code: 'TEMPLATE_NOT_FOUND', message: 'That template no longer exists.' } } })
      const card = (await screen.findAllByTestId('library-card'))[0]

      fireEvent.click(within(card).getByRole('button', { name: 'Use this set' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('That template no longer exists.')
      expect(onApplied).not.toHaveBeenCalled()
      expect(onClose).not.toHaveBeenCalled()
      expect(within(card).getByRole('button', { name: 'Use this set' })).toBeEnabled() // can try another
    })

    it('cannot be started twice by a double click', async () => {
      renderLibrary()
      let finish
      api.post.mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
      const card = (await screen.findAllByTestId('library-card'))[0]
      const use = within(card).getByRole('button', { name: 'Use this set' })

      fireEvent.click(use)
      fireEvent.click(use)

      expect(api.post).toHaveBeenCalledTimes(1)
      expect(use).toBeDisabled()
      finish({ data: { questions: [] } })
      await waitFor(() => expect(use).toBeEnabled())
    })
  })

  describe('a company set', () => {
    const openMine = async () => {
      const result = renderLibrary()
      await screen.findAllByTestId('library-card')
      fireEvent.click(tab("My company's sets"))
      return result
    }

    it('is renamed in place', async () => {
      await openMine()
      api.patch.mockResolvedValueOnce({ data: { ...MINE, name: 'Sales, first round' } })

      fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Rename Our sales set' }))
      fireEvent.change(screen.getByLabelText('New name'), { target: { value: 'Sales, first round' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save the new name' }))

      expect(await screen.findByText('Sales, first round')).toBeInTheDocument()
      expect(api.patch).toHaveBeenCalledWith(`${LIBRARY}/t-1`, { name: 'Sales, first round' })
      expect(screen.queryByLabelText('New name')).not.toBeInTheDocument()
    })

    it('keeps the old name and says why when the new one is taken', async () => {
      await openMine()
      api.patch.mockRejectedValueOnce({ response: { status: 422, data: { code: 'TEMPLATE_NAME_TAKEN', message: 'Your company already has a template with that name. Choose another name, or delete the old one.' } } })

      fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Rename Our sales set' }))
      fireEvent.change(screen.getByLabelText('New name'), { target: { value: 'Finance set' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save the new name' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('already has a template with that name')
      expect(screen.getByLabelText('New name')).toHaveValue('Finance set') // still editing
    })

    it('can be left unrenamed', async () => {
      await openMine()

      fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Rename Our sales set' }))
      fireEvent.click(screen.getByRole('button', { name: 'Cancel renaming' }))

      expect(screen.queryByLabelText('New name')).not.toBeInTheDocument()
      expect(api.patch).not.toHaveBeenCalled()
    })

    it('is deleted after asking, and disappears from the list', async () => {
      await openMine()
      api.delete.mockResolvedValueOnce({})

      fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Delete Our sales set' }))

      await waitFor(() => expect(screen.queryByText('Our sales set')).not.toBeInTheDocument())
      expect(confirmSpy).toHaveBeenCalledWith('Delete "Our sales set"? Jobs already started from it are not affected.')
      expect(api.delete).toHaveBeenCalledWith(`${LIBRARY}/t-1`)
      expect(screen.getByText('Finance set')).toBeInTheDocument()
    })

    it('is not deleted when the employer declines', async () => {
      await openMine()
      confirmSpy.mockReturnValue(false)

      fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Delete Our sales set' }))

      expect(api.delete).not.toHaveBeenCalled()
      expect(screen.getByText('Our sales set')).toBeInTheDocument()
    })

    it('stays in the list, with the server\'s words, when the delete fails', async () => {
      await openMine()
      api.delete.mockRejectedValueOnce({ response: { status: 403, data: { code: 'FORBIDDEN', message: 'Only the person who saved a template, or the company owner, can delete it.' } } })

      fireEvent.click(within(cards()[0]).getByRole('button', { name: 'Delete Our sales set' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Only the person who saved a template')
      expect(screen.getByText('Our sales set')).toBeInTheDocument()
    })
  })

  it('says the library could not be loaded, rather than showing it empty', async () => {
    api.get.mockRejectedValue(new Error('network'))
    renderLibrary()

    expect(await screen.findByRole('alert')).toHaveTextContent('The library could not be loaded.')
    expect(screen.queryByTestId('library-empty')).not.toBeInTheDocument()
  })

  it('closes from the cross and from the Close button', async () => {
    const { onClose } = renderLibrary()
    await screen.findAllByTestId('library-card')

    fireEvent.click(screen.getByRole('button', { name: 'Close the library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
