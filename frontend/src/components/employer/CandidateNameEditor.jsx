import { useState } from 'react'
import { Pencil, Loader2 } from 'lucide-react'
import api from '@/lib/api'

const MAX_NAME_CHARS = 120

/**
 * CandidateNameEditor - a sourced candidate's name with a pencil to correct it, for when the name
 * read from the CV is wrong. The typed name replaces the CV's name everywhere the candidate is
 * shown (the CV itself is not changed); "Use the name from the CV" takes it away again.
 *
 * `name` is what is shown now, `overridden` whether that is a typed name, `onSaved` gets the
 * server's `{ candidate_name, name_overridden }` so the parent can show it at once. `nameClassName`
 * styles the name where the parent already has a look for it.
 */
export default function CandidateNameEditor({
  profileId,
  name,
  overridden = false,
  onSaved,
  nameClassName = '',
  fallback = 'Unnamed candidate',
}) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const open = () => {
    setValue(name ?? '')
    setError(null)
    setEditing(true)
  }

  const save = async (next) => {
    if (saving) return
    setSaving(true)
    setError(null)
    try {
      const { data } = await api.patch(`/api/v1/talent-pool/${profileId}/name`, { name: next })
      onSaved?.(data)
      setEditing(false)
    } catch (err) {
      const message = err?.response?.data?.message
      setError(
        err?.response
          ? (typeof message === 'string' ? message : 'Something went wrong. Please try again.')
          : 'We could not reach the server. Check your connection and try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  const trimmed = value.trim()
  const tooLong = trimmed.length > MAX_NAME_CHARS
  const unchanged = trimmed === (name ?? '').trim()

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5 min-w-0">
        <span className={nameClassName}>{name || fallback}</span>
        {overridden && (
          <span className="text-[10px] font-medium text-text-muted" title="This name was typed in by your team, not read from the CV">
            (corrected)
          </span>
        )}
        <button
          type="button"
          onClick={open}
          aria-label="Correct the name"
          title="Correct the name"
          className="text-text-muted hover:text-brand-blue flex-shrink-0"
        >
          <Pencil size={12} aria-hidden="true" />
        </button>
      </span>
    )
  }

  return (
    <form
      className="space-y-1.5 w-full max-w-sm"
      onSubmit={(event) => {
        event.preventDefault()
        if (!tooLong && !unchanged) save(trimmed || null)
      }}
    >
      <label className="block text-[11px] font-medium text-text-muted" htmlFor={`name-${profileId}`}>
        Candidate&apos;s name
      </label>
      <input
        id={`name-${profileId}`}
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        autoFocus
        maxLength={MAX_NAME_CHARS + 20}
        className="w-full rounded-lg border border-border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
      />
      {tooLong && <p className="text-[11px] text-red-600">Use {MAX_NAME_CHARS} characters or fewer.</p>}
      {error && (
        <p role="alert" className="text-[11px] text-red-600">
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="submit"
          disabled={saving || tooLong || unchanged}
          className="inline-flex items-center gap-1 rounded-lg bg-brand-blue px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-50"
        >
          {saving && <Loader2 size={11} className="animate-spin" aria-hidden="true" />}
          Save name
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          disabled={saving}
          className="text-xs font-medium text-text-muted hover:text-text"
        >
          Cancel
        </button>
        {overridden && (
          <button
            type="button"
            onClick={() => save(null)}
            disabled={saving}
            className="text-xs font-medium text-brand-blue hover:underline"
          >
            Use the name from the CV
          </button>
        )}
      </div>
    </form>
  )
}
