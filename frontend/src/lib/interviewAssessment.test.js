import { describe, it, expect } from 'vitest'
import { parseAssessment } from './interviewAssessment'

describe('parseAssessment', () => {
  it('splits a summary from its Strengths and Weaknesses lists', () => {
    const text =
      'A confident communicator.\n\nStrengths:\n- Clear examples\n- Good structure\n\nWeaknesses:\n- Light on numbers'

    expect(parseAssessment(text)).toEqual({
      summary: ['A confident communicator.'],
      sections: [
        { title: 'Strengths', items: ['Clear examples', 'Good structure'] },
        { title: 'Weaknesses', items: ['Light on numbers'] },
      ],
    })
  })

  it('keeps the other sections the AI can add, in order', () => {
    const text = 'Summary.\n\nNot covered in this interview:\n- Pricing\n\nContradictions:\n- Said ten, then twelve'

    expect(parseAssessment(text).sections.map((s) => s.title)).toEqual([
      'Not covered in this interview',
      'Contradictions',
    ])
  })

  it('keeps several summary paragraphs', () => {
    expect(parseAssessment('First paragraph.\n\nSecond paragraph.').summary).toEqual([
      'First paragraph.',
      'Second paragraph.',
    ])
  })

  it('joins a wrapped paragraph into one line', () => {
    expect(parseAssessment('One line\nwrapped over two.').summary).toEqual(['One line wrapped over two.'])
  })

  it('treats text that has no lists as a summary only', () => {
    expect(parseAssessment('Just a summary.')).toEqual({ summary: ['Just a summary.'], sections: [] })
  })

  it('gives nothing for no text', () => {
    expect(parseAssessment(null)).toEqual({ summary: [], sections: [] })
    expect(parseAssessment('')).toEqual({ summary: [], sections: [] })
  })

  it('does not mistake a sentence ending in a colon for a heading when no list follows', () => {
    expect(parseAssessment('Overall the candidate said this:').summary).toEqual([
      'Overall the candidate said this:',
    ])
  })
})
