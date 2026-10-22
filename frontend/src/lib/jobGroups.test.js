import { describe, it, expect } from 'vitest'
import { groupJobsByStatus } from './jobGroups'

const job = (id, status) => ({ id, title: `Job ${id}`, status })

describe('groupJobsByStatus', () => {
  it('puts active jobs first, then drafts, each in the order given', () => {
    const groups = groupJobsByStatus([
      job('d1', 'DRAFT'),
      job('a1', 'ACTIVE'),
      job('d2', 'DRAFT'),
      job('a2', 'ACTIVE'),
    ])

    expect(groups.map((g) => g.label)).toEqual(['Active', 'Drafts (not yet published)'])
    expect(groups[0].jobs.map((j) => j.id)).toEqual(['a1', 'a2'])
    expect(groups[1].jobs.map((j) => j.id)).toEqual(['d1', 'd2'])
  })

  it('leaves out a group with nothing in it', () => {
    expect(groupJobsByStatus([job('a1', 'ACTIVE')]).map((g) => g.label)).toEqual(['Active'])
    expect(groupJobsByStatus([job('d1', 'DRAFT')]).map((g) => g.label)).toEqual([
      'Drafts (not yet published)',
    ])
    expect(groupJobsByStatus([])).toEqual([])
    expect(groupJobsByStatus(undefined)).toEqual([])
  })

  it('hides closed jobs, which are noise in a picker, unless one is the job already chosen', () => {
    const jobs = [job('a1', 'ACTIVE'), job('c1', 'CLOSED'), job('c2', 'CLOSED')]

    expect(groupJobsByStatus(jobs).map((g) => g.label)).toEqual(['Active'])

    const withChosen = groupJobsByStatus(jobs, 'c2')
    expect(withChosen.map((g) => g.label)).toEqual(['Active', 'Closed'])
    expect(withChosen[1].jobs.map((j) => j.id)).toEqual(['c2'])
  })

  it('treats a job the plan switched off like a closed one: it takes no applications', () => {
    const jobs = [job('a1', 'ACTIVE'), job('s1', 'DISABLED')]

    expect(groupJobsByStatus(jobs).map((g) => g.label)).toEqual(['Active'])

    const withChosen = groupJobsByStatus(jobs, 's1')
    expect(withChosen.map((g) => g.label)).toEqual(['Active', 'Closed'])
    expect(withChosen[1].jobs.map((j) => j.id)).toEqual(['s1'])
  })

  it('treats a job with no known status like an active one, as the picker always has', () => {
    const groups = groupJobsByStatus([{ id: 'x', title: 'No status' }])

    expect(groups).toHaveLength(1)
    expect(groups[0].label).toBe('Active')
  })
})
