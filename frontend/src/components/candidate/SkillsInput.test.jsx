import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { SkillsInput } from './SkillsInput'

// The input as the profile page uses it: the list lives in the parent.
function Harness({ initial = [], onChange = () => {}, onSubmit = () => {} }) {
  const [skills, setSkills] = useState(initial)
  return (
    <form onSubmit={(event) => { event.preventDefault(); onSubmit() }}>
      <SkillsInput value={skills} onChange={(next) => { setSkills(next); onChange(next) }} />
      <output data-testid="skills">{skills.join('|')}</output>
      <button type="submit">Save</button>
    </form>
  )
}

const field = () => screen.getByLabelText('Add a skill')
const type = (text) => fireEvent.change(field(), { target: { value: text } })
const shown = () => screen.getByTestId('skills').textContent

describe('SkillsInput, adding a skill', () => {
  it('adds a skill when Enter is pressed', () => {
    render(<Harness />)
    type('Negotiation')

    fireEvent.keyDown(field(), { key: 'Enter' })

    expect(shown()).toBe('Negotiation')
    expect(field()).toHaveValue('')
  })

  it('adds a skill when a comma is typed', () => {
    render(<Harness />)

    type('Negotiation,')

    expect(shown()).toBe('Negotiation')
    expect(field()).toHaveValue('')
  })

  it('adds a skill with the Add button, which is what a tablet has no Enter key for', () => {
    render(<Harness />)
    type('Negotiation')

    fireEvent.click(screen.getByRole('button', { name: 'Add skill' }))

    expect(shown()).toBe('Negotiation')
    expect(field()).toHaveValue('')
  })

  it('has an Add button that waits until something is typed', () => {
    render(<Harness />)
    const add = screen.getByRole('button', { name: 'Add skill' })

    expect(add).toBeDisabled()
    type('   ')
    expect(add).toBeDisabled()
    type('Sales')
    expect(add).toBeEnabled()
  })

  it('adds what was typed when the person leaves the field, so tapping Save does not lose it', () => {
    render(<Harness />)
    type('Negotiation')

    fireEvent.blur(field())

    expect(shown()).toBe('Negotiation')
  })

  it('does not add anything when the person leaves an empty field', () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)

    fireEvent.blur(field())
    type('   ')
    fireEvent.blur(field())

    expect(onChange).not.toHaveBeenCalled()
  })

  it('understands a keyboard that reports only the key code, as some on-screen keyboards do', () => {
    render(<Harness />)
    type('Negotiation')

    fireEvent.keyDown(field(), { key: 'Unidentified', keyCode: 13 })

    expect(shown()).toBe('Negotiation')
  })

  it('understands a comma reported only by its key code', () => {
    render(<Harness />)
    type('Negotiation')

    fireEvent.keyDown(field(), { key: 'Unidentified', keyCode: 188 })

    expect(shown()).toBe('Negotiation')
  })

  it('keeps every skill of a pasted list, not just the last', () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)

    type('Sales, Negotiation, Excel, Presenting')

    expect(shown()).toBe('Sales|Negotiation|Excel')
    expect(field()).toHaveValue(' Presenting')
    expect(onChange).toHaveBeenCalledTimes(1)
    fireEvent.blur(field())
    expect(shown()).toBe('Sales|Negotiation|Excel|Presenting')
  })

  it('splits a list pasted one skill to a line', () => {
    render(<Harness />)

    fireEvent.paste(field(), { clipboardData: { getData: () => 'Sales\nNegotiation\nExcel\n' } })

    expect(shown()).toBe('Sales|Negotiation|Excel')
    expect(field()).toHaveValue('')
  })

  it('splits a pasted comma list in one go too, joining the first item to what was already typed', () => {
    render(<Harness />)
    type('Pre')

    fireEvent.paste(field(), { clipboardData: { getData: () => 'fix, Sales' } })

    expect(shown()).toBe('Prefix|Sales')
  })

  it('leaves an ordinary paste of one skill to the field', () => {
    render(<Harness />)

    const paste = new Event('paste', { bubbles: true, cancelable: true })
    paste.clipboardData = { getData: () => 'Negotiation' }
    field().dispatchEvent(paste)

    expect(paste.defaultPrevented).toBe(false)
  })

  it('ignores a skill that is already there, whatever its case, and an empty one', () => {
    render(<Harness initial={['Sales']} />)

    type('sales')
    fireEvent.keyDown(field(), { key: 'Enter' })
    type('   ')
    fireEvent.keyDown(field(), { key: 'Enter' })
    type(',,')

    expect(shown()).toBe('Sales')
  })

  it('trims the blanks around a skill', () => {
    render(<Harness />)
    type('   Project   management  ')

    fireEvent.keyDown(field(), { key: 'Enter' })

    expect(shown()).toBe('Project   management')
  })
})

describe('SkillsInput, the profile form around it', () => {
  it('does not save the profile when Enter is pressed in the skills field', () => {
    const onSubmit = vi.fn()
    render(<Harness onSubmit={onSubmit} />)
    type('Negotiation')

    const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    field().dispatchEvent(enter)

    expect(enter.defaultPrevented).toBe(true)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('does not save the profile either when Enter is pressed with nothing typed', () => {
    render(<Harness />)

    const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    field().dispatchEvent(enter)

    expect(enter.defaultPrevented).toBe(true)
  })

  it('has the Add button and the remove buttons stay buttons that never submit the form', () => {
    const onSubmit = vi.fn()
    render(<Harness initial={['Sales']} onSubmit={onSubmit} />)
    type('Excel')

    fireEvent.click(screen.getByRole('button', { name: 'Add skill' }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove skill: Sales' }))

    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('SkillsInput, removing a skill', () => {
  it('removes a skill with its button', () => {
    render(<Harness initial={['Sales', 'Excel']} />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove skill: Sales' }))

    expect(shown()).toBe('Excel')
  })

  it('removes the last skill with Backspace on an empty field, and not while typing', () => {
    render(<Harness initial={['Sales', 'Excel']} />)

    type('Pre')
    fireEvent.keyDown(field(), { key: 'Backspace' })
    expect(shown()).toBe('Sales|Excel')

    type('')
    fireEvent.keyDown(field(), { key: 'Backspace' })
    expect(shown()).toBe('Sales')
  })
})

describe('SkillsInput, what the person is told', () => {
  it('says to tap Add, not only to press Enter', () => {
    render(<Harness />)

    expect(field().getAttribute('placeholder')).toMatch(/tap Add/)
  })

  it('asks the on-screen keyboard for a Done key and for no autocorrect on skill names', () => {
    render(<Harness />)

    expect(field()).toHaveAttribute('enterkeyhint', 'done')
    expect(field()).toHaveAttribute('autocorrect', 'off')
  })

  it('is written the way the rest of the product is: no dashes, no exclamation marks', () => {
    render(<Harness />)

    expect(field().getAttribute('placeholder')).not.toMatch(/[–—!]/)
  })
})
