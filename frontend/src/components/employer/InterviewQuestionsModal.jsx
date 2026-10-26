import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Loader2, Plus, Sparkles, Trash2, X } from 'lucide-react'
import api from '@/lib/api'
import {
  MAX_QUESTION_CHARS,
  TIME_OPTIONS,
  blankQuestion,
  formatSeconds,
  moveQuestion,
  problemsWith,
  removeQuestion,
  totalSeconds,
} from '@/lib/interviewQuestions'

// The server's own words when it sent any (its messages name the problem and the limit).
function serverMessage(err, fallback) {
  const body = err?.response?.data
  const detail = body?.details?.map((item) => item.message).filter(Boolean).join(' ')
  const message = detail || body?.message || body?.detail
  return typeof message === 'string' ? message : fallback
}

/**
 * InterviewQuestionsModal - a job's list of strict-interview questions: the same questions go to
 * every candidate. The AI can draft the list from the interview brief; the employer reads it,
 * changes anything, sets the time each question gets, and saves. A draft is never saved on its
 * own.
 *
 * Shown only when the platform's interview style is "strict" (see InterviewListTab).
 */
export default function InterviewQuestionsModal({ jobId, hasBrief, onClose, onSaved }) {
  const nextKey = useRef(0)
  const newKey = useCallback(() => `q${nextKey.current++}`, [])

  const [status, setStatus] = useState('loading') // loading | ready | error
  const [limits, setLimits] = useState(null)
  const [questions, setQuestions] = useState([])
  const [dirty, setDirty] = useState(false)
  const [drafting, setDrafting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get(`/api/v1/interviews/jobs/${jobId}/questions`)
      .then(({ data }) => {
        if (cancelled) return
        setLimits(data)
        setQuestions(data.questions.map((item) => ({ ...item, key: item.id })))
        setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [jobId])

  const edit = (updater) => {
    setQuestions(updater)
    setDirty(true)
    setNotice(null)
  }

  const change = (index, field, value) =>
    edit((list) =>
      list.map((question, position) =>
        // Anything the employer changes is now theirs, not the AI's.
        position === index ? { ...question, [field]: value, source: 'EMPLOYER' } : question
      )
    )

  // Tagging a question with a competency does not make it the employer's own wording, so it keeps
  // its "AI draft" mark.
  const tag = (index, competency) =>
    edit((list) => list.map((question, position) => (position === index ? { ...question, competency } : question)))

  const close = () => {
    if (dirty && !window.confirm('You have unsaved changes. Close without saving?')) return
    onClose()
  }

  const draft = async () => {
    if (questions.length > 0 && !window.confirm('Replace your current questions with a new draft?')) return
    setDrafting(true)
    setError(null)
    setNotice(null)
    try {
      const { data } = await api.post(`/api/v1/interviews/jobs/${jobId}/questions/draft`, {})
      setQuestions(data.questions.map((item) => ({ ...item, key: newKey() })))
      setDirty(true)
      setNotice(
        `Drafted ${data.questions.length} question${data.questions.length === 1 ? '' : 's'}. Read them, change anything you like, then save.`
      )
    } catch (err) {
      setError(serverMessage(err, 'We could not draft the questions just now. Please try again, or write them yourself.'))
    } finally {
      setDrafting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const { data } = await api.put(`/api/v1/interviews/jobs/${jobId}/questions`, {
        questions: questions.map(({ text, time_limit_seconds, source, competency }) => ({
          text,
          time_limit_seconds,
          source,
          competency: competency || null,
        })),
      })
      onSaved?.(data)
      onClose()
    } catch (err) {
      setError(serverMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const problems = limits ? problemsWith(questions, limits) : []
  const total = totalSeconds(questions)
  const overTime = limits ? total > limits.max_total_seconds : false
  const atLimit = limits ? questions.length >= limits.max_questions : false
  // The standard closing question is already in the list (the draft adds it, or it was added
  // here), so it is not offered twice. Matched on its text, which the employer may have edited.
  const hasClosing = Boolean(
    limits?.closing_question && questions.some((q) => q.text.trim() === limits.closing_question.text),
  )
  // The job's scoring profile: its competencies (for the tag on each question) and, as the tags
  // change, which weighted competencies no question tests.
  const competencies = limits?.competencies ?? []
  const untested = competencies.filter((name) => !questions.some((q) => q.competency === name))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Interview questions"
        className="flex max-h-full w-full max-w-2xl flex-col rounded-xl border border-border bg-white"
      >
        <div className="flex items-start justify-between gap-4 p-6 pb-3">
          <div>
            <h2 className="text-lg font-bold text-text">Interview questions</h2>
            <p className="text-sm text-text-muted mt-1">
              Every candidate gets these same questions, in this order, and answers each one by
              speaking to the camera. The AI may ask a follow-up when an answer needs one.
            </p>
          </div>
          <button type="button" onClick={close} className="text-text-muted hover:text-text flex-shrink-0" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 pb-2">
          {status === 'loading' && (
            <p className="flex items-center gap-2 text-sm text-text-muted">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </p>
          )}

          {status === 'error' && (
            <p role="alert" className="text-sm text-red-600">
              The questions could not be loaded. Please close this and try again.
            </p>
          )}

          {status === 'ready' && (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={draft}
                  disabled={!hasBrief || drafting}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-brand-blue px-3 py-1.5 text-xs font-semibold text-brand-blue transition-colors hover:bg-brand-blue/5 disabled:opacity-50"
                >
                  {drafting ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                  {drafting ? 'Drafting…' : 'Draft from the interview brief'}
                </button>
                {!hasBrief && (
                  <span className="text-xs text-text-muted">
                    Write the interview brief first. The questions are drafted from it.
                  </span>
                )}
              </div>

              {notice && (
                <p role="status" className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800">
                  {notice}
                </p>
              )}

              {questions.length === 0 && (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
                  No questions yet. Draft them from the brief, or add your own.
                </p>
              )}

              <ol className="space-y-3">
                {questions.map((question, index) => (
                  <li key={question.key} className="space-y-2 rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <label htmlFor={`question-${question.key}`} className="text-xs font-semibold text-text">
                        Question {index + 1}
                        {question.source === 'AI' && (
                          <span className="ml-2 rounded-full bg-brand-blue/10 px-2 py-0.5 text-[10px] font-medium text-brand-blue">
                            AI draft
                          </span>
                        )}
                      </label>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => edit((list) => moveQuestion(list, index, -1))}
                          disabled={index === 0}
                          aria-label={`Move question ${index + 1} up`}
                          className="rounded p-1 text-text-muted hover:bg-surface-muted disabled:opacity-30"
                        >
                          <ArrowUp size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => edit((list) => moveQuestion(list, index, 1))}
                          disabled={index === questions.length - 1}
                          aria-label={`Move question ${index + 1} down`}
                          className="rounded p-1 text-text-muted hover:bg-surface-muted disabled:opacity-30"
                        >
                          <ArrowDown size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => edit((list) => removeQuestion(list, index))}
                          aria-label={`Remove question ${index + 1}`}
                          className="rounded p-1 text-red-600 hover:bg-red-50"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <textarea
                      id={`question-${question.key}`}
                      value={question.text}
                      onChange={(event) => change(index, 'text', event.target.value)}
                      rows={2}
                      maxLength={MAX_QUESTION_CHARS + 50}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                    />
                    <div className="flex items-center gap-2">
                      <label htmlFor={`time-${question.key}`} className="text-xs text-text-muted">
                        Time to answer
                      </label>
                      <select
                        id={`time-${question.key}`}
                        value={question.time_limit_seconds}
                        onChange={(event) => change(index, 'time_limit_seconds', Number(event.target.value))}
                        className="rounded-lg border border-border bg-white px-2 py-1 text-xs"
                      >
                        {TIME_OPTIONS.map((seconds) => (
                          <option key={seconds} value={seconds}>
                            {formatSeconds(seconds)}
                          </option>
                        ))}
                      </select>
                    </div>
                    {competencies.length > 0 && (
                      <div className="flex items-center gap-2">
                        <label htmlFor={`competency-${question.key}`} className="text-xs text-text-muted">
                          Tests competency
                        </label>
                        <select
                          id={`competency-${question.key}`}
                          value={question.competency ?? ''}
                          onChange={(event) => tag(index, event.target.value || null)}
                          className="min-w-0 flex-1 rounded-lg border border-border bg-white px-2 py-1 text-xs"
                        >
                          <option value="">Not tagged</option>
                          {competencies.map((name) => (
                            <option key={name} value={name}>{name}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </li>
                ))}
              </ol>

              {competencies.length > 0 && untested.length > 0 && (
                <p role="note" data-testid="untested-competencies" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  No question is tagged with: {untested.join(', ')}. A competency nobody is asked about
                  can only be assessed if an answer happens to cover it, and the score is then incomplete.
                </p>
              )}

              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => edit((list) => [...list, blankQuestion(newKey())])}
                    disabled={atLimit}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text transition-colors hover:bg-surface-muted disabled:opacity-50"
                  >
                    <Plus size={13} /> Add a question
                  </button>
                  {limits.closing_question && (
                    <button
                      type="button"
                      onClick={() =>
                        edit((list) => [
                          ...list,
                          { ...blankQuestion(newKey()), ...limits.closing_question },
                        ])
                      }
                      disabled={atLimit || hasClosing}
                      title="Asks about motivation, notice period, start date and pay, which the scorecard collects at the end. You can change or remove it."
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text transition-colors hover:bg-surface-muted disabled:opacity-50"
                    >
                      <Plus size={13} /> Add the standard closing question
                    </button>
                  )}
                </div>
                <span className="text-xs text-text-muted">
                  {questions.length} of {limits.max_questions} questions
                </span>
              </div>

              <p className={overTime ? 'text-xs font-medium text-red-600' : 'text-xs text-text-muted'}>
                Answer time: {formatSeconds(total)} of {formatSeconds(limits.max_total_seconds)}. The
                interview ends after {formatSeconds(limits.max_total_seconds)} in all, and any follow-up
                questions use part of that time.
              </p>

              {problems.length > 0 && (
                <ul className="space-y-0.5 text-xs text-red-600" aria-label="Problems with the list">
                  {problems.map((problem) => (
                    <li key={problem}>{problem}</li>
                  ))}
                </ul>
              )}
              {error && (
                <p role="alert" className="text-xs text-red-600">
                  {error}
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-2 p-6 pt-3">
          <button
            type="button"
            onClick={close}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold text-text-muted transition-colors hover:bg-surface-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={status !== 'ready' || saving || !dirty || problems.length > 0}
            className="rounded-lg bg-brand-blue px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-blue/90 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save questions'}
          </button>
        </div>
      </div>
    </div>
  )
}
