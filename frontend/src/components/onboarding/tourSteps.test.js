import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { CANDIDATE_STEPS, EMPLOYER_STEPS, EXAMPLE_JOB_STEPS } from './tourSteps'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const DASHBOARD = read('../../pages/DashboardPage.jsx')
const CANDIDATE_DASHBOARD = read('../../pages/candidate/CandidateDashboardPage.jsx')
const EXAMPLE_PAGE = read('../../pages/employer/ExampleJobTourPage.jsx')

// The dashboard's tabs get their data-tour from the tab id.
const DASHBOARD_TAB_IDS = [...DASHBOARD.matchAll(/\{ id: '([a-z-]+)', label:/g)].map((m) => m[1])

function isOnPage(target, source) {
  if (source.includes(`data-tour="${target}"`)) return true
  return target.startsWith('tab-') && DASHBOARD_TAB_IDS.includes(target.slice(4))
}

const ALL = [
  ...EMPLOYER_STEPS.map((s) => ({ ...s, source: DASHBOARD, where: 'the dashboard' })),
  ...EXAMPLE_JOB_STEPS.map((s) => ({ ...s, source: EXAMPLE_PAGE, where: 'the example job page' })),
  ...CANDIDATE_STEPS.map((s) => ({ ...s, source: CANDIDATE_DASHBOARD, where: 'the candidate dashboard' })),
]

describe('tour steps', () => {
  it.each(ALL.map((s) => [`${s.title} (${s.where})`, s]))('%s points at an element that exists', (_name, step) => {
    expect(isOnPage(step.target, step.source)).toBe(true)
  })

  it.each(ALL.map((s) => [s.title, s]))('"%s" is written the way the emails are: plain, no dashes, no hype', (_name, step) => {
    const text = `${step.title} ${step.description} ${step.nextLabel ?? ''}`
    expect(text).not.toMatch(/[–—]/) // en and em dashes
    expect(text).not.toMatch(/!/)
    expect(text).not.toMatch(/\b(seamless|powerful|supercharge|unlock|leverage|effortless)/i)
    expect(step.title).toMatch(/^[A-Z]/)
    expect(step.title).not.toMatch(/\b[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+/) // not Title Case
  })

  it('the candidate guide says what makes a profile complete and where the CV goes', () => {
    const text = CANDIDATE_STEPS.map((s) => s.description).join(' ')

    for (const item of ['About you', 'Skills', 'Years of experience', 'Location', 'CV']) {
      expect(text).toContain(item)
    }
    expect(text).toContain('My Documents')
    expect(text).toContain('PDF')
    expect(text).toContain('5MB')
  })

  it('the employer tour covers every part the product owner asked for', () => {
    const titles = [...EMPLOYER_STEPS, ...EXAMPLE_JOB_STEPS].map((s) => s.title.toLowerCase()).join(' | ')

    for (const topic of [
      'post a job', 'manage your jobs', 'applicants', 'match score', 'add people to the interview list',
      'upload cvs', 'talent pool', 'choose the job to score against', 'interview list',
      'send interviews', 'costs', 'candidate search', 'credits',
    ]) {
      expect(titles).toContain(topic)
    }
  })

  it('exactly one dashboard step moves on to the example job', () => {
    expect(EMPLOYER_STEPS.filter((s) => s.handoff)).toHaveLength(1)
    expect(EMPLOYER_STEPS[EMPLOYER_STEPS.length - 1].handoff).toBe(true)
  })
})
