import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, BookmarkPlus, Library, Loader2, Plus, Sparkles, Trash2, X } from 'lucide-react'
import api from '@/lib/api'
import QuestionLibraryModal from '@/components/employer/QuestionLibraryModal'
import {
  DEFAULT_FOLLOW_UP_SECONDS,
  FOLLOW_UP_MODES,
  FOLLOW_UP_TIME_OPTIONS,
  LITTLE_TIME_FOR_FOLLOW_UPS,
  MAX_QUESTION_CHARS,
  TIME_OPTIONS,
  blankQuestion,
  formatSeconds,
  moveQuestion,
  probeLines,
  problemsWith,
  removeQuestion,
  timeLeftForFollowUps,
  totalSeconds,
} from '@/lib/interviewQuestions'

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

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
  // What the AI may do after an answer, for the whole job: STANDARD | PROBES_ONLY | NONE.
  const [followUpMode, setFollowUpMode] = useState('STANDARD')
  const [drafting, setDrafting] = useState(false)
  // The ready-made role set chosen in the picker, and whether it is being loaded.
  const [libraryOpen, setLibraryOpen] = useState(false)
  // The "Save as template" form: its name, whether the scoring profile goes with it, and saving.
  const [saveFormOpen, setSaveFormOpen] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateWithProfile, setTemplateWithProfile] = useState(true)
  const [savingTemplate, setSavingTemplate] = useState(false)
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
        setFollowUpMode(data.follow_up_mode ?? 'STANDARD')
        setQuestions(data.questions.map((item) => ({ ...item, probes: item.probes ?? '', key: item.id })))
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

  // Probes are extra, not the question's own wording, so they too keep the "AI draft" mark.
  const setProbes = (index, probes) =>
    edit((list) => list.map((question, position) => (position === index ? { ...question, probes } : question)))

  // One question at most is the practical case, so ticking one unticks any other.
  const setPractical = (index, isPractical) =>
    edit((list) =>
      list.map((question, position) =>
        position === index
          ? { ...question, is_practical: isPractical }
          : isPractical
            ? { ...question, is_practical: false }
            : question
      )
    )

  const setFollowUpSeconds = (index, follow_up_seconds) =>
    edit((list) =>
      list.map((question, position) => (position === index ? { ...question, follow_up_seconds } : question))
    )

  // A set chosen in the template library (the Colton Group's, the company's own, or another job's)
  // has been put on the job: its scoring profile AND questions with their probes, saved at once,
  // replacing what the job has. The employer can then change anything and save again.
  const handleApplied = (data, name) => {
    setLibraryOpen(false)
    setError(null)
    setLimits(data)
    setFollowUpMode(data.follow_up_mode ?? 'STANDARD')
    setQuestions(data.questions.map((item) => ({ ...item, probes: item.probes ?? '', key: newKey() })))
    const count = plural(data.questions.length, 'question')
    if (data.saved === false) {
      // The answer times of the set add up to more than the interview's time limit, so it could
      // not be saved: it is shown for the employer to shorten (the red message below says by how
      // much, and stays until it fits). Its scoring profile is already set.
      setDirty(true)
      setNotice(
        `Loaded "${name}": ${count}. The answer times are longer than the interview allows, so the questions are not saved yet. Shorten some of the times, then save.`
      )
    } else {
      setDirty(false) // it is saved already
      setNotice(`Loaded "${name}": ${count}. It is saved. Change anything you like, then save again.`)
      onSaved?.(data)
    }
  }

  // Keep the questions as they are on the screen as a template the whole company can use. The answer
  // times need not fit this job's time limit; applying it to a job shows it for shortening if not.
  const saveAsTemplate = async () => {
    setSavingTemplate(true)
    setError(null)
    setNotice(null)
    try {
      const { data } = await api.post('/api/v1/interviews/question-templates', {
        job_id: jobId,
        name: templateName,
        include_profile: templateWithProfile,
        follow_up_mode: followUpMode,
        questions: questions.map(({ text, time_limit_seconds, source, competency, probes, follow_up_seconds, is_practical }) => ({
          text,
          time_limit_seconds,
          source,
          competency: competency || null,
          probes: probes || null,
          follow_up_seconds: follow_up_seconds ?? null,
          is_practical: Boolean(is_practical),
        })),
      })
      setSaveFormOpen(false)
      setTemplateName('')
      setNotice(
        `Saved "${data.name}" for your whole company${data.has_scoring_profile ? ', with the scoring profile' : ''}. Find it in the template library, under "My company's sets".`
      )
    } catch (err) {
      setError(serverMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setSavingTemplate(false)
    }
  }

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
      setQuestions(data.questions.map((item) => ({ ...item, probes: item.probes ?? '', key: newKey() })))
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
        questions: questions.map(({ text, time_limit_seconds, source, competency, probes, follow_up_seconds, is_practical }) => ({
          text,
          time_limit_seconds,
          source,
          competency: competency || null,
          probes: probes || null,
          follow_up_seconds: follow_up_seconds ?? null,
          is_practical: Boolean(is_practical),
        })),
        follow_up_mode: followUpMode,
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
  // What stops a list being kept as a template: the same rules, except the total time, because a
  // template is not tied to one job's time limit.
  const problemsExceptTime = limits ? problemsWith(questions, { ...limits, max_total_seconds: Infinity }) : []
  const total = totalSeconds(questions)
  const overTime = limits ? total > limits.max_total_seconds : false
  // A follow-up is asked only when what is left of the interview still covers every later question,
  // so a list that uses nearly all the time leaves no room for one: say so.
  const timeLeft = limits ? timeLeftForFollowUps(questions, limits) : 0
  const littleTimeForFollowUps =
    followUpMode !== 'NONE' && questions.length > 0 && !overTime && timeLeft < LITTLE_TIME_FOR_FOLLOW_UPS
  // With "Only my probes", a question with no probe never gets a follow-up: say so, so it is not a surprise.
  const noProbesAtAll = followUpMode === 'PROBES_ONLY' && questions.every((q) => probeLines(q.probes).length === 0)
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
              speaking to the camera. Below the questions you choose what happens after an answer.
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

              {/* The template library: ready-made sets to start from, and keeping this one for later */}
              <div className="space-y-2 rounded-lg border border-border bg-surface-muted/40 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setLibraryOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-brand-blue px-3 py-1.5 text-xs font-semibold text-brand-blue transition-colors hover:bg-brand-blue/5"
                  >
                    <Library size={13} /> Browse templates
                  </button>
                  <button
                    type="button"
                    onClick={() => setSaveFormOpen((value) => !value)}
                    disabled={questions.length === 0 || problemsExceptTime.length > 0}
                    aria-expanded={saveFormOpen}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text transition-colors hover:bg-surface-muted disabled:opacity-50"
                  >
                    <BookmarkPlus size={13} /> Save as template
                  </button>
                  <span className="text-xs text-text-muted">
                    Start from the Colton Group sets, your company&apos;s own, or another job.
                  </span>
                </div>
                {saveFormOpen && (
                  <div className="space-y-2 border-t border-border pt-2" data-testid="save-template-form">
                    <label htmlFor="template-name" className="text-xs font-semibold text-text">Name this template</label>
                    <input
                      id="template-name"
                      value={templateName}
                      onChange={(event) => setTemplateName(event.target.value)}
                      maxLength={120}
                      placeholder="For example: Sales Manager, first interview"
                      className="w-full rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                    />
                    {competencies.length > 0 && (
                      <label className="flex items-start gap-2 text-xs text-text-muted">
                        <input
                          type="checkbox"
                          checked={templateWithProfile}
                          onChange={(event) => setTemplateWithProfile(event.target.checked)}
                          className="mt-0.5"
                        />
                        <span>Include this job&apos;s scoring profile, so the tags and weights come with the questions.</span>
                      </label>
                    )}
                    <p className="text-xs text-text-muted">
                      Everyone in your company can use it. It keeps the questions as they are on the screen now,
                      with their probes, times, follow-up choice and practical case.
                    </p>
                    <button
                      type="button"
                      onClick={saveAsTemplate}
                      disabled={!templateName.trim() || savingTemplate}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-blue/90 disabled:opacity-50"
                    >
                      {savingTemplate && <Loader2 size={13} className="animate-spin" />}
                      {savingTemplate ? 'Saving…' : 'Save template'}
                    </button>
                  </div>
                )}
              </div>
              {libraryOpen && (
                <QuestionLibraryModal
                  jobId={jobId}
                  hasQuestions={questions.length > 0}
                  onApplied={handleApplied}
                  onClose={() => setLibraryOpen(false)}
                />
              )}

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
                            Drafted
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
                    <label className="flex items-start gap-2 text-xs text-text-muted">
                      <input
                        type="checkbox"
                        checked={Boolean(question.is_practical)}
                        onChange={(event) => setPractical(index, event.target.checked)}
                        aria-label={`Mark question ${index + 1} as the practical case`}
                        className="mt-0.5"
                      />
                      <span>
                        <span className="font-semibold text-text">Practical case.</span> A scenario the
                        candidate works through aloud, scored on its own out of 5 and not part of the weighted score.
                      </span>
                    </label>
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
                    {followUpMode !== 'NONE' && (
                      <div className="space-y-1">
                        <label htmlFor={`probes-${question.key}`} className="text-xs text-text-muted">
                          {followUpMode === 'PROBES_ONLY'
                            ? 'Follow-up probes that may be asked (one per line)'
                            : 'Your own follow-up probes (optional, one per line)'}
                        </label>
                        <textarea
                          id={`probes-${question.key}`}
                          value={question.probes ?? ''}
                          onChange={(event) => setProbes(index, event.target.value)}
                          rows={2}
                          placeholder="For example: What was your own part in it?"
                          className="w-full rounded-lg border border-border px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                        />
                        <div className="flex items-center gap-2">
                          <label htmlFor={`follow-up-time-${question.key}`} className="text-xs text-text-muted">
                            Time to answer a follow-up
                          </label>
                          <select
                            id={`follow-up-time-${question.key}`}
                            value={question.follow_up_seconds ?? DEFAULT_FOLLOW_UP_SECONDS}
                            onChange={(event) => setFollowUpSeconds(index, Number(event.target.value))}
                            className="rounded-lg border border-border bg-white px-2 py-1 text-xs"
                          >
                            {FOLLOW_UP_TIME_OPTIONS.map((seconds) => (
                              <option key={seconds} value={seconds}>
                                {formatSeconds(seconds)}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )}
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
                      disabled={hasClosing}
                      title="Asks about motivation, notice period, start date and pay, which the scorecard collects at the end. You can change or remove it."
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text transition-colors hover:bg-surface-muted disabled:opacity-50"
                    >
                      <Plus size={13} /> Add the standard closing question
                    </button>
                  )}
                </div>
                <span className="text-xs text-text-muted">
                  {questions.length} question{questions.length === 1 ? '' : 's'}
                </span>
              </div>

              {/* What the AI does after an answer: the same for every candidate of this job */}
              <fieldset className="space-y-2 rounded-lg border border-border p-3">
                <legend className="px-1 text-xs font-semibold text-text">After an answer, the interviewer may</legend>
                {FOLLOW_UP_MODES.map((mode) => (
                  <label key={mode.value} className="flex cursor-pointer items-start gap-2">
                    <input
                      type="radio"
                      name="follow-up-mode"
                      value={mode.value}
                      checked={followUpMode === mode.value}
                      onChange={() => {
                        setFollowUpMode(mode.value)
                        setDirty(true)
                        setNotice(null)
                      }}
                      className="mt-0.5"
                    />
                    <span className="text-xs">
                      <span className="font-semibold text-text">{mode.label}</span>
                      <span className="block text-text-muted">{mode.help}</span>
                    </span>
                  </label>
                ))}
                <p className="text-xs text-text-muted">
                  The candidate is shown this in the rules before they start, and every candidate of the job gets the same.
                </p>
                {noProbesAtAll && (
                  <p role="note" data-testid="no-probes-note" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    No question has a probe yet, so no follow-up will be asked. Write probes under the
                    questions, or choose another option.
                  </p>
                )}
              </fieldset>

              <p className={overTime ? 'text-xs font-medium text-red-600' : 'text-xs text-text-muted'}>
                Answer time: {formatSeconds(total)} of {formatSeconds(limits.max_total_seconds)}. The
                interview ends after {formatSeconds(limits.max_total_seconds)} in all, and any follow-up
                questions use part of that time.
              </p>

              {littleTimeForFollowUps && (
                <p role="note" data-testid="little-time-for-follow-ups" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  Only {formatSeconds(timeLeft)} of the {formatSeconds(limits.max_total_seconds)} is left after the
                  answer times. A follow-up is asked only when time is left for every question still to come, so
                  few or none will be asked. Shorten some of the times to leave more room.
                </p>
              )}

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

        <div className="flex items-center justify-end gap-2 p-6 pt-3">
          {status === 'ready' && problems.length > 0 && (
            <p data-testid="cannot-save-note" className="mr-auto text-xs font-medium text-red-600">
              {overTime ? 'Shorten the answer times to save.' : 'Fix the problems above to save.'}
            </p>
          )}
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
