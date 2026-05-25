import { useState, useRef } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * SkillsInput — tag chip input for managing a list of skill strings.
 *
 * Props:
 *   value    — string[]  current list of skills
 *   onChange — (skills: string[]) => void  called when the list changes
 *
 * A skill is added when the user presses Enter or types a comma.
 * A skill is removed by clicking its × button.
 *
 * Requirements: 11.9
 */
export function SkillsInput({ value = [], onChange }) {
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef(null)

  // Add a skill, trimming whitespace and ignoring duplicates/empty strings
  function addSkill(raw) {
    const skill = raw.trim().replace(/,$/, '').trim()
    if (!skill) return
    if (value.includes(skill)) {
      setInputValue('')
      return
    }
    onChange([...value, skill])
    setInputValue('')
  }

  // Requirement 11.9 — add on Enter or comma keypress
  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addSkill(inputValue)
    }
    // Backspace on empty input removes the last chip
    if (e.key === 'Backspace' && inputValue === '' && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  function handleChange(e) {
    const raw = e.target.value
    // If the user pastes or types a comma mid-word, split immediately
    if (raw.includes(',')) {
      const parts = raw.split(',')
      // Everything before the last comma is a skill to add
      parts.slice(0, -1).forEach((part) => addSkill(part))
      // Keep whatever is after the last comma in the input
      setInputValue(parts[parts.length - 1])
    } else {
      setInputValue(raw)
    }
  }

  // Requirement 11.9 — remove a skill by clicking its chip button
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
          {/* Requirement 11.9 — remove button */}
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
        type="text"
        value={inputValue}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={value.length === 0 ? 'Type a skill and press Enter or comma…' : ''}
        aria-label="Add a skill"
        className="flex-1 min-w-[140px] bg-transparent outline-none placeholder:text-text-muted text-text"
      />
    </div>
  )
}
