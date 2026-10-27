import { describe, it, expect } from 'vitest'
import { blankCompetency, problemsWith, rowsFrom, toRequest, totalWeight } from './scoringProfile'

const BANDS = { strong: 85, shortlist: 75, hold: 65 }
const row = (name, weight, isKey = false) => ({ key: name, name, weight, isKey })
const VALID = [row('Strategy', 60, true), row('P&L', 40)]

describe('totalWeight', () => {
  it('adds the weights and counts a blank or a non-number as zero', () => {
    expect(totalWeight([row('A', 25), row('B', 30), row('C', '')])).toBe(55)
    expect(totalWeight([row('A', 'x'), row('B', 10)])).toBe(10)
    expect(totalWeight([])).toBe(0)
  })
})

describe('problemsWith', () => {
  it('has none for a profile that can be saved', () => {
    expect(problemsWith(VALID, BANDS, 3)).toEqual([])
  })

  it.each([
    [[row('A', 60), row('B', 30)], 'add up to 90%, and must add up to 100%'],
    [[row('A', 100)], 'between 2 and 12'],
    [Array.from({ length: 13 }, (_, i) => row(`C${i}`, 1)), 'between 2 and 12'],
    [[row('A', 50), row('a ', 50)], '"a" is listed twice'],
    [[row('  ', 50), row('B', 50)], 'Competency 1 needs a name'],
    [[row('A', 0), row('B', 100)], 'whole-number weight from 1 to 100'],
    [[row('A', 50.5), row('B', 49.5)], 'whole-number weight'],
    [[row('A', ''), row('B', 100)], 'whole-number weight'],
    [[row('A'.repeat(81), 50), row('B', 50)], 'name over 80 characters'],
  ])('names what is wrong with %j', (rows, fragment) => {
    expect(problemsWith(rows, BANDS, 3).join(' ')).toContain(fragment)
  })

  it.each([
    [{ strong: 70, shortlist: 75, hold: 65 }, 'must go down'],
    [{ strong: 85, shortlist: 85, hold: 65 }, 'must go down'],
    [{ strong: 101, shortlist: 75, hold: 65 }, 'whole numbers from 1 to 100'],
    [{ strong: 85, shortlist: 75, hold: '' }, 'whole numbers from 1 to 100'],
  ])('checks the bands %j', (bands, fragment) => {
    expect(problemsWith(VALID, bands, 3).join(' ')).toContain(fragment)
  })

  it('checks the minimum rating for a key competency', () => {
    expect(problemsWith(VALID, BANDS, 0).join(' ')).toContain('from 1 to 5')
    expect(problemsWith(VALID, BANDS, 6).join(' ')).toContain('from 1 to 5')
    expect(problemsWith(VALID, BANDS, 5)).toEqual([])
  })
})

describe('rows and the request', () => {
  it('turns a template or a saved profile into editor rows with their own keys and a key flag', () => {
    let n = 0
    const rows = rowsFrom([{ name: 'A', weight: 60, key: true }, { name: 'B', weight: 40 }], () => `k${n++}`)

    expect(rows).toEqual([
      { key: 'k0', name: 'A', weight: 60, isKey: true },
      { key: 'k1', name: 'B', weight: 40, isKey: false },
    ])
  })

  it('makes an empty competency with a blank weight', () => {
    expect(blankCompetency('x')).toEqual({ key: 'x', name: '', weight: '', isKey: false })
  })

  it('builds the request with tidy names, whole weights, numbers for the thresholds and the template', () => {
    const request = toRequest(
      [row('  Brand   strategy ', '25', true), row('P&L', 75)],
      { strong: '85', shortlist: 75, hold: '65' },
      '3',
      'commercial_director',
    )

    expect(request).toEqual({
      competencies: [
        { name: 'Brand strategy', weight: 25, key: true },
        { name: 'P&L', weight: 75, key: false },
      ],
      bands: { strong: 85, shortlist: 75, hold: 65 },
      key_min_rating: 3,
      template_code: 'commercial_director',
    })
    expect(toRequest(VALID, BANDS, 3, '').template_code).toBeNull()
  })
})
