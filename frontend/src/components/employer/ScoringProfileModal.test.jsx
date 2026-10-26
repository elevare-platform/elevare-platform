import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import api from '@/lib/api'
import ScoringProfileModal from './ScoringProfileModal'

const URL = '/api/v1/interviews/jobs/job-1/scoring-profile'
const TEMPLATES = [
  {
    code: 'commercial_director',
    title: 'Commercial Director',
    competencies: [
      { name: 'Commercial strategy and profitable growth', weight: 25, key: true },
      { name: 'P&L, pricing and financial management', weight: 20, key: true },
      { name: 'Route-to-market and distribution strategy', weight: 20, key: false },
      { name: 'Leadership and organisational development', weight: 15, key: false },
      { name: 'Brand and portfolio management', weight: 10, key: false },
      { name: 'Cross-functional execution', weight: 10, key: false },
    ],
  },
  { code: 'national_sales_manager', title: 'National Sales Manager', competencies: [{ name: 'A', weight: 60, key: true }, { name: 'B', weight: 40, key: false }] },
]
const BASE = {
  profile: null,
  templates: TEMPLATES,
  default_bands: { strong: 85, shortlist: 75, hold: 65 },
  default_key_min_rating: 3,
}
const SAVED = {
  ...BASE,
  profile: {
    competencies: [{ name: 'Strategy', weight: 70, key: true }, { name: 'Execution', weight: 30, key: false }],
    bands: { strong: 90, shortlist: 80, hold: 70 },
    key_min_rating: 4,
    template_code: null,
  },
}

function renderModal(data = BASE) {
  api.get.mockResolvedValue({ data })
  const onClose = vi.fn()
  const onSaved = vi.fn()
  render(<ScoringProfileModal jobId="job-1" onClose={onClose} onSaved={onSaved} />)
  return { onClose, onSaved }
}

const save = () => screen.getByRole('button', { name: 'Save scoring profile' })
const pick = (code) => fireEvent.change(screen.getByLabelText('Start from a template'), { target: { value: code } })

describe('ScoringProfileModal', () => {
  let confirmSpy
  beforeEach(() => {
    vi.clearAllMocks()
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => confirmSpy.mockRestore())

  it('starts empty for a job with no profile, offering the templates and the default bands', async () => {
    renderModal()

    expect(await screen.findByText(/No competencies yet/)).toBeInTheDocument()
    expect(screen.getByLabelText('Strong shortlist from')).toHaveValue(85)
    expect(screen.getByLabelText('Shortlist from')).toHaveValue(75)
    expect(screen.getByLabelText('Hold for evidence from')).toHaveValue(65)
    expect(screen.getByLabelText('Minimum rating for key competencies')).toHaveValue('3')
    expect(save()).toBeDisabled()
  })

  it('fills in a template with its weights and key ones, adding up to 100%', async () => {
    renderModal()
    await screen.findByLabelText('Start from a template')

    pick('commercial_director')

    expect(screen.getByLabelText('Competency 1 name')).toHaveValue('Commercial strategy and profitable growth')
    expect(screen.getByLabelText('Competency 1 weight')).toHaveValue(25)
    expect(screen.getByLabelText('Competency 1 is key')).toBeChecked()
    expect(screen.getByLabelText('Competency 3 is key')).not.toBeChecked()
    expect(screen.getByTestId('weight-total')).toHaveTextContent('Weights: 100% of 100%')
    expect(save()).toBeEnabled()
  })

  it('sends the template, the bands and the key minimum when saved, then closes', async () => {
    api.put.mockResolvedValue({ data: BASE })
    const { onClose, onSaved } = renderModal()
    await screen.findByLabelText('Start from a template')
    pick('national_sales_manager')

    fireEvent.click(save())

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.put).toHaveBeenCalledWith(URL, {
      competencies: [{ name: 'A', weight: 60, key: true }, { name: 'B', weight: 40, key: false }],
      bands: { strong: 85, shortlist: 75, hold: 65 },
      key_min_rating: 3,
      template_code: 'national_sales_manager',
    })
    expect(onSaved).toHaveBeenCalled()
  })

  it('asks before replacing competencies that are already there with a template', async () => {
    confirmSpy.mockReturnValue(false)
    renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')

    pick('commercial_director')

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Replace your competencies'))
    expect(screen.getByLabelText('Competency 1 name')).toHaveValue('Strategy')
  })

  it('shows the weights in red until they add up to 100, says so, and will not save', async () => {
    renderModal()
    await screen.findByLabelText('Start from a template')
    pick('national_sales_manager')

    fireEvent.change(screen.getByLabelText('Competency 2 weight'), { target: { value: '30' } })

    expect(screen.getByTestId('weight-total')).toHaveTextContent('Weights: 90% of 100%')
    expect(screen.getByTestId('weight-total').className).toContain('text-red-600')
    expect(screen.getByTestId('profile-problems')).toHaveTextContent('The weights add up to 90%, and must add up to 100%.')
    expect(save()).toBeDisabled()
  })

  it('adds and removes competencies and counts the weights as they change', async () => {
    renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')

    fireEvent.click(screen.getByRole('button', { name: /Add a competency/ }))
    fireEvent.change(screen.getByLabelText('Competency 3 name'), { target: { value: 'Leadership' } })
    fireEvent.change(screen.getByLabelText('Competency 3 weight'), { target: { value: '10' } })
    expect(screen.getByTestId('weight-total')).toHaveTextContent('Weights: 110% of 100%')

    fireEvent.click(screen.getByRole('button', { name: 'Remove competency 3' }))
    expect(screen.getByTestId('weight-total')).toHaveTextContent('Weights: 100% of 100%')
  })

  it('checks the band thresholds go down', async () => {
    renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')

    fireEvent.change(screen.getByLabelText('Shortlist from'), { target: { value: '95' } })

    expect(screen.getByTestId('profile-problems')).toHaveTextContent('must go down')
    expect(save()).toBeDisabled()
  })

  it('says the bands are provisional and that a key competency never rejects anyone', async () => {
    renderModal()

    expect(await screen.findByText('Suggested bands (provisional)')).toBeInTheDocument()
    expect(screen.getByText(/not validated cutoffs/)).toBeInTheDocument()
    expect(screen.getByText(/It never rejects anyone: a person decides\./)).toBeInTheDocument()
  })

  it('shows a saved profile as it was saved, with its own bands and key minimum', async () => {
    renderModal(SAVED)

    expect(await screen.findByLabelText('Competency 2 name')).toHaveValue('Execution')
    expect(screen.getByLabelText('Strong shortlist from')).toHaveValue(90)
    expect(screen.getByLabelText('Minimum rating for key competencies')).toHaveValue('4')
    expect(screen.getByRole('button', { name: 'Remove the scoring profile' })).toBeInTheDocument()
  })

  it('shows the server\'s words when it refuses, and keeps the editor open', async () => {
    api.put.mockRejectedValue({ response: { data: { message: 'The weights add up to 90%.', details: [{ message: 'The weights add up to 90%.' }] } } })
    const { onClose } = renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')
    fireEvent.change(screen.getByLabelText('Competency 1 name'), { target: { value: 'Strategy and growth' } })

    fireEvent.click(save())

    expect(await screen.findByText('The weights add up to 90%.')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('removes the profile after asking, and tells the page', async () => {
    api.delete.mockResolvedValue({ data: BASE })
    const { onClose, onSaved } = renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')

    fireEvent.click(screen.getByRole('button', { name: 'Remove the scoring profile' }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('generic scorecard'))
    expect(api.delete).toHaveBeenCalledWith(URL)
    expect(onSaved).toHaveBeenCalled()
  })

  it('does not offer to remove a profile that does not exist', async () => {
    renderModal()
    await screen.findByLabelText('Start from a template')

    expect(screen.queryByRole('button', { name: 'Remove the scoring profile' })).not.toBeInTheDocument()
  })

  it('asks before closing with unsaved changes', async () => {
    confirmSpy.mockReturnValue(false)
    const { onClose } = renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')
    fireEvent.change(screen.getByLabelText('Competency 1 name'), { target: { value: 'Changed' } })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('unsaved changes'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('says it could not load when the server cannot be reached', async () => {
    api.get.mockRejectedValue(new Error('network'))
    render(<ScoringProfileModal jobId="job-1" onClose={vi.fn()} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
  })

  it('has no save button enabled before anything is changed', async () => {
    renderModal(SAVED)
    await screen.findByLabelText('Competency 1 name')

    expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Save scoring profile' })).toBeDisabled()
  })
})
