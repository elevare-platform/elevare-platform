import { useState, useRef } from 'react'
import { Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * SkillsInput - tag chip input for managing a list of skill strings.
 *
 * Props:
 *   value   - string[]  current list of skills
 *   onChange - (skills: string[]) => void  called when the list changes
 *
 * A skill is added three ways, so it works on a keyboard AND on a tablet or phone, whose
 * on-screen keyboards do not always send an Enter or comma key press the page can see:
 *   - Enter or a comma,
 *   - the Add button (a tap),
 *   - leaving the field with something typed in it (tapping Save, say), so a skill that was
 *     typed is never lost just because Enter was not pressed.
 * A skill is removed by clicking its × button. Several skills can be pasted at once, separated
 * by commas or on separate lines.
 *
 * Requirements: 11.9
 */
export function SkillsInput({ value = [], onChange }) {
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef(null)

  // Add skills, trimming whitespace and ignoring empty strings and duplicates (case does not
  // matter: "sales" and "Sales" are one skill). One change, however many were added, so a
  // pasted list is never cut down to its last item.
  function addSkills(raws) {
    const known = new Set(value.map((skill) => skill.toLowerCase()))
    const added = []
    for (const raw of raws) {
      const skill = raw.trim()
      if (!skill || known.has(skill.toLowerCase())) continue
      known.add(skill.toLowerCase())
      added.push(skill)
    }
    setInputValue('')
    if (added.length > 0) onChange([...value, ...added])
  }

  // Requirement 11.9-  add on Enter or comma keypress
  function handleKeyDown(e) {
    // keyCode is checked too: some on-screen keyboards report only that.
    const isEnter = e.key === 'Enter' || e.keyCode === 13
    const isComma = e.key === ',' || e.keyCode === 188
    if (isEnter || isComma) {
      // Always stopped, even with nothing typed: Enter here must never submit the profile form.
      e.preventDefault()
      addSkills([inputValue])
    }
    // Backspace on empty input removes the last chip
    if (e.key === 'Backspace' && inputValue === '' && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  function handleChange(e) {
    const raw = e.target.value
    // A comma (typed, or in pasted text) ends a skill straight away.
    if (raw.includes(',')) {
      const parts = raw.split(',')
      // Everything before the last comma is a skill to add; what follows stays in the input.
      addSkills(parts.slice(0, -1))
      setInputValue(parts[parts.length - 1])
    } else {
      setInputValue(raw)
    }
  }

  // A list pasted with commas or one skill to a line becomes several skills. (A single-line
  // field drops new lines from pasted text, so they have to be read from the clipboard here.)
  function handlePaste(e) {
    const text = e.clipboardData?.getData('text') ?? ''
    if (!/[,\n]/.test(text)) return
    e.preventDefault()
    const [first, ...rest] = text.split(/[,\n]/)
    addSkills([inputValue + first, ...rest])
  }

  // Leaving the field with a skill typed in adds it.
  function handleBlur() {
    if (inputValue.trim()) addSkills([inputValue])
  }

  // Requirement 11.9-  remove a skill by clicking its chip button
  function removeSkill(skill) {
    onChange(value.filter((s) => s !== skill))
  }

  // Clicking anywhere in the container focuses the text input
  function handleContainerClick() {
    inputRef.current?.focus()
  }

  return (
    <div
      role="group"
      aria-label="Skills"
      onClick={handleContainerClick}
      className={cn(
        'flex flex-wrap gap-2 items-center min-h-[42px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm',
        'focus-within:outline-none focus-within:ring-2 focus-within:ring-brand-blue focus-within:border-brand-blue',
        'cursor-text',
      )}
    >
      {/* Existing skill chips */}
      {value.map((skill) => (
        <span
          key={skill}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-blue/10 text-brand-blue text-xs font-medium"
        >
          {skill}
          {/* Requirement 11.9-  remove button */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              removeSkill(skill)
            }}
            aria-label={`Remove skill: ${skill}`}
            className="ml-0.5 rounded-full hover:bg-brand-blue/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-blue transition-colors"
          >
            <X size={11} aria-hidden="true" />
          </button>
        </span>
      ))}

      {/* Text input for new skills */}
      <input
        ref={inputRef}
        id="skills-input"
        type="text"
        value={inputValue}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        onPaste={handlePaste}
        placeholder={value.length === 0 ? 'Type a skill, then tap Add…' : ''}
        aria-label="Add a skill"
        enterKeyHint="done"
        autoCapitalize="words"
        autoComplete="off"
        autoCorrect="off"
        className="flex-1 min-w-[140px] bg-transparent outline-none placeholder:text-text-muted text-text"
      />

      {/* A tap target for screens with no Enter key to press. */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          addSkills([inputValue])
          inputRef.current?.focus()
        }}
        disabled={!inputValue.trim()}
        aria-label="Add skill"
        className="inline-flex items-center gap-1 rounded-md border border-brand-blue px-2.5 py-1 text-xs font-semibold text-brand-blue transition-colors hover:bg-brand-blue/5 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus size={12} aria-hidden="true" />
        Add
      </button>
    </div>
  )
}
