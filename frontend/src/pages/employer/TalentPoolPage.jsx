import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Upload, X, FileText, RefreshCw, ChevronDown, UserPlus,
  Briefcase, Zap, Users, TrendingUp, Search, Filter,
  CheckCircle2, Clock, Archive, Star, ChevronRight,
  BarChart3, Brain, AlertCircle, ExternalLink,
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { useToast } from '@/components/admin/Toast'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Constants ───────────────────────────────────────────────────────────────

const SOURCES = ['email', 'referral', 'linkedin', 'other']
const STATUSES = ['new', 'shortlisted', 'promoted_pending', 'promoted', 'archived']

const STATUS_CONFIG = {
  new:              { label: 'New',             icon: Clock,         color: 'bg-blue-100 text-blue-700 border-blue-200' },
  shortlisted:      { label: 'Shortlisted',     icon: Star,          color: 'bg-green-100 text-green-700 border-green-200' },
  promoted_pending: { label: 'Invite Sent',     icon: Clock,         color: 'bg-amber-100 text-amber-700 border-amber-200' },
  promoted:         { label: 'Promoted',        icon: CheckCircle2,  color: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  archived:         { label: 'Archived',        icon: Archive,       color: 'bg-gray-100 text-gray-500 border-gray-200' },
}

const SOURCE_ICONS = {
  email: '📧', referral: '🤝', linkedin: '💼', other: '📎',
}

function scoreColor(score) {
  if (score == null) return 'bg-gray-100 text-gray-400 border-gray-200'
  if (score >= 75) return 'bg-green-100 text-green-700 border-green-200'
  if (score >= 50) return 'bg-amber-100 text-amber-700 border-amber-200'
  return 'bg-red-100 text-red-600 border-red-200'
}

function ScoreBadge({ score }) {
  return (
    <div className={cn(
      'w-12 h-12 rounded-full border-2 flex items-center justify-center text-sm font-bold flex-shrink-0',
      scoreColor(score)
    )}>
      {score != null ? score : '—'}
    </div>
  )
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status]
  if (!cfg) return null
  const Icon = cfg.icon
  return (
    <span className={cn('inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border', cfg.color)}>
      <Icon size={10} />
      {cfg.label}
    </span>
  )
}

// ─── Upload Drawer ────────────────────────────────────────────────────────────

function UploadDrawer({ open, onClose, onUploaded, jobs }) {
  const dropRef = useRef(null)
  const [files, setFiles] = useState([])
  const [source, setSource] = useState('other')
  const [sourceNote, setSourceNote] = useState('')
  const [jobId, setJobId] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState([])
  const [progress, setProgress] = useState(null) // { done, total } for polling
  const [error, setError] = useState(null)

  const reset = () => {
    setFiles([]); setSourceNote(''); setJobId('')
    setError(null); setResults([]); setProgress(null)
  }

  const addFiles = (newFiles) => {
    const pdfs = newFiles.filter(f => f.type === 'application/pdf')
    setFiles(prev => [...prev, ...pdfs].slice(0, 20))
  }

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false)
    addFiles(Array.from(e.dataTransfer.files))
  }

  // Poll submission statuses until all reach a terminal state
  const pollUntilDone = useCallback(async (submissionIds) => {
    const TERMINAL = ['completed', 'failed', 'flagged']
    const total = submissionIds.length
    const pending = new Set(submissionIds)

    setProgress({ done: 0, total })

    while (pending.size > 0) {
      await new Promise(r => setTimeout(r, 2500))
      for (const sid of [...pending]) {
        try {
          const { data } = await api.get(`/api/v1/ai/cv-parsing/${sid}`)
          if (TERMINAL.includes(data.parse_status)) {
            pending.delete(sid)
            setProgress(p => ({ ...p, done: total - pending.size }))
          }
        } catch { pending.delete(sid) }
      }
    }
    setProgress(p => ({ ...p, done: total }))
    onUploaded()
  }, [onUploaded])

  const handleSubmit = async () => {
    if (!files.length) return
    setUploading(true); setError(null); setResults([])
    try {
      const form = new FormData()
      files.forEach(f => form.append('files', f))
      form.append('source', source)
      if (sourceNote) form.append('source_note', sourceNote)
      if (jobId) form.append('sourced_for_job_id', jobId)
      const { data } = await api.post('/api/v1/talent-pool/submit-batch', form)
      const batchResults = data.results ?? []
      setResults(batchResults)
      setFiles([])

      // Start polling for queued submissions
      const submissionIds = batchResults
        .filter(r => r.status === 'queued' && r.submission_id)
        .map(r => r.submission_id)
      if (submissionIds.length > 0) {
        pollUntilDone(submissionIds)
      } else {
        onUploaded()
      }
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      if (status === 413) {
        setError('Files are too large. Each CV should be under 10 MB — try compressing or splitting the batch.')
      } else if (status === 415 || (typeof detail === 'string' && detail.toLowerCase().includes('pdf'))) {
        setError('Only PDF files are accepted. Please check your files and try again.')
      } else if (status === 429) {
        setError('Too many uploads. Please wait a moment and try again.')
      } else if (status === 422) {
        setError('Invalid request — please check your files and form fields.')
      } else if (status >= 500) {
        setError('Server error. Our team has been notified — please try again shortly.')
      } else {
        setError(detail ?? 'Upload failed. Please try again.')
      }
    } finally {
      setUploading(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />
      <div
        className="relative ml-auto w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl flex flex-col"
        onClick={e => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-label="Add to Talent Pool"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-border">
          <div>
            <h2 className="font-semibold text-text text-base">Add to Talent Pool</h2>
            <p className="text-xs text-text-muted mt-0.5">Upload up to 20 CVs — batch processed</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 px-6 py-6 space-y-5">
          {/* Drop zone */}
          <div
            ref={dropRef}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById('tp-drawer-file').click()}
            className={cn(
              'rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-200',
              dragging ? 'border-brand-blue bg-brand-blue/5 scale-[1.01]' : 'border-border hover:border-brand-blue/50 hover:bg-surface-muted'
            )}
          >
            <div className="w-12 h-12 rounded-xl bg-brand-blue/10 flex items-center justify-center mx-auto mb-3">
              <Upload size={20} className="text-brand-blue" />
            </div>
            <p className="text-sm font-medium text-text mb-1">Drop PDFs here</p>
            <p className="text-xs text-text-muted">
              {files.length > 0 ? `${files.length} file${files.length > 1 ? 's' : ''} selected` : <>or <span className="text-brand-blue font-medium">browse files</span> · up to 20</>}
            </p>
            <input id="tp-drawer-file" type="file" accept="application/pdf" multiple className="sr-only"
              onChange={e => addFiles(Array.from(e.target.files))} />
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="space-y-1.5 max-h-40 overflow-y-auto">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-white text-sm">
                  <FileText size={13} className="text-brand-blue flex-shrink-0" />
                  <span className="flex-1 truncate text-text text-xs">{f.name}</span>
                  <span className="text-xs text-text-muted">{(f.size / 1024).toFixed(0)} KB</span>
                  <button type="button" onClick={e => { e.stopPropagation(); setFiles(prev => prev.filter((_, j) => j !== i)) }}
                    className="text-text-muted hover:text-red-500 transition-colors">
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Batch results */}
          {results.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">Results</p>
              {results.map((r, i) => (
                <div key={i} className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-lg border text-xs',
                  r.status === 'queued'
                    ? 'border-green-200 bg-green-50 text-green-700'
                    : r.status === 'duplicate'
                    ? 'border-amber-200 bg-amber-50 text-amber-700'
                    : 'border-red-200 bg-red-50 text-red-700'
                )}>
                  {r.status === 'queued'
                    ? <CheckCircle2 size={12} />
                    : r.status === 'duplicate'
                    ? <AlertCircle size={12} />
                    : <AlertCircle size={12} />}
                  <span className="flex-1 truncate">{r.filename}</span>
                  <span>
                    {r.status === 'queued'
                      ? 'Queued'
                      : r.status === 'duplicate'
                      ? 'Already in pool'
                      : r.error}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Parsing progress bar */}
          {progress && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>
                  {progress.done < progress.total
                    ? `Parsing & scoring… ${progress.done} / ${progress.total}`
                    : `All ${progress.total} CV${progress.total > 1 ? 's' : ''} processed`}
                </span>
                <span>{Math.round((progress.done / progress.total) * 100)}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-surface-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-brand-blue transition-all duration-500"
                  style={{ width: `${(progress.done / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Source */}
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 block">Source</label>
            <div className="grid grid-cols-2 gap-2">
              {SOURCES.map(s => (
                <button key={s} type="button" onClick={() => setSource(s)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm font-medium transition-all',
                    source === s
                      ? 'border-brand-blue bg-brand-blue/5 text-brand-blue'
                      : 'border-border text-text-muted hover:border-brand-blue/40 hover:text-text'
                  )}>
                  <span>{SOURCE_ICONS[s]}</span>
                  <span className="capitalize">{s}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Job attachment */}
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 block">
              Attach to Job <span className="normal-case font-normal">(optional — enables immediate scoring)</span>
            </label>
            <div className="relative">
              <select value={jobId} onChange={e => setJobId(e.target.value)}
                className="w-full text-sm rounded-lg border border-border px-3 py-2.5 pr-8 appearance-none focus:outline-none focus:ring-2 focus:ring-brand-blue bg-white">
                <option value="">No job — add to pipeline only</option>
                {(jobs ?? []).map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
            </div>
            {jobId && (
              <p className="text-xs text-green-600 mt-1.5 flex items-center gap-1">
                <Zap size={11} /> AI scoring will run automatically after parsing
              </p>
            )}
          </div>

          {/* Note */}
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 block">Source note (optional)</label>
            <input value={sourceNote} onChange={e => setSourceNote(e.target.value)}
              placeholder="e.g. Referred by John Doe via LinkedIn"
              className="w-full text-sm rounded-lg border border-border px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-blue" />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
              {error}
            </div>
          )}
        </div>

        <div className="px-6 py-5 border-t border-border space-y-2">
          <Button onClick={handleSubmit} disabled={!files.length || uploading} className="w-full" size="lg">
            {uploading
              ? `Uploading ${files.length} CV${files.length > 1 ? 's' : ''}…`
              : files.length > 0
                ? `Add ${files.length} CV${files.length > 1 ? 's' : ''} to Talent Pool`
                : 'Add to Talent Pool'}
          </Button>
          {results.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <button
                onClick={() => { onUploaded(); onClose() }}
                className="w-full text-xs font-medium text-brand-blue hover:text-brand-blue-dark transition-colors py-1.5 rounded-lg border border-brand-blue/20 hover:bg-brand-blue/5"
              >
                Run in background — close drawer
              </button>
              <button onClick={() => { reset(); onClose() }} className="w-full text-xs text-text-muted hover:text-text transition-colors py-1">
                Done — close drawer
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── View CV Button ───────────────────────────────────────────────────────────

function ViewCvButton({ submissionId }) {
  const [loading, setLoading] = useState(false)
  const [errMsg, setErrMsg] = useState(null)

  const handleClick = async (e) => {
    e.stopPropagation()
    if (!submissionId) return
    setLoading(true)
    setErrMsg(null)
    try {
      const { data } = await api.get(`/api/v1/cv-parsing/submissions/${submissionId}/download`)
      window.open(typeof data === 'string' ? data : data.url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      const status = err.response?.status
      if (status === 425) {
        setErrMsg('Still processing — try again in a few seconds.')
      } else if (status === 404) {
        setErrMsg('CV file not found.')
      } else {
        setErrMsg('Could not open CV.')
      }
      setTimeout(() => setErrMsg(null), 4000)
    } finally {
      setLoading(false)
    }
  }

  if (!submissionId) return null
  return (
    <div className="relative flex flex-col items-end">
      <button
        onClick={handleClick}
        disabled={loading}
        title="View CV"
        className="flex items-center gap-1 text-xs font-medium text-text-muted hover:text-brand-blue transition-colors disabled:opacity-50"
      >
        {loading ? <RefreshCw size={12} className="animate-spin" /> : <ExternalLink size={12} />}
        <span>CV</span>
      </button>
      {errMsg && (
        <span className="absolute top-5 right-0 z-10 whitespace-nowrap rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs px-2.5 py-1.5 shadow-sm">
          {errMsg}
        </span>
      )}
    </div>
  )
}

// ─── Candidate Card (job-scoped ranked view) ──────────────────────────────────

function CandidateCard({ profile, rank, isAdmin, onPromote, onStatusChange }) {
  const [expanded, setExpanded] = useState(false)

  const hasReasoning = profile.ai_fit_summary || profile.ai_strengths?.length > 0

  return (
    <div className={cn(
      'group rounded-xl border bg-white overflow-hidden transition-all duration-200',
      'hover:shadow-md hover:border-brand-blue/20',
      expanded ? 'shadow-md border-brand-blue/20' : 'border-border'
    )}>
      <div className="flex items-center gap-4 p-4">
        {/* Rank */}
        <div className="w-7 h-7 rounded-full bg-surface-muted text-text-muted text-xs font-bold flex items-center justify-center flex-shrink-0">
          {rank}
        </div>

        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-blue/20 to-brand-blue/5 flex items-center justify-center flex-shrink-0">
          <Users size={16} className="text-brand-blue" />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-text text-sm">
              {profile.candidate_name ?? profile.candidate_email ?? `Unidentified · ${profile.id.slice(0, 8)}`}
            </p>
            <span className="text-xs text-text-muted capitalize flex items-center gap-1">
              {SOURCE_ICONS[profile.source]} {profile.source}
            </span>
          </div>
          <p className="text-xs text-text-muted mt-0.5">
            {[profile.candidate_current_title, profile.candidate_email].filter(Boolean).join(' · ') ||
              `Added ${new Date(profile.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`
            }
          </p>
        </div>

        {/* Score */}
        <ScoreBadge score={profile.ai_score} />

        {/* Status */}
        <StatusBadge status={profile.status} />

        {/* Actions */}
        <div className="flex items-center gap-2">
          {!['promoted', 'promoted_pending'].includes(profile.status) && (
            <div className="relative">
              <select value="" onChange={e => { if (e.target.value) onStatusChange(profile.id, e.target.value) }}
                className="appearance-none text-xs rounded-lg border border-border bg-white pl-2.5 pr-7 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-blue cursor-pointer">
                <option value="" disabled>Move to…</option>
                {STATUSES.filter(s => s !== profile.status && !['promoted', 'promoted_pending'].includes(s)).map(s => (
                  <option key={s} value={s}>{STATUS_CONFIG[s]?.label ?? s}</option>
                ))}
              </select>
              <ChevronDown size={10} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted" />
            </div>
          )}

          {isAdmin && profile.status === 'shortlisted' && (
            <button onClick={() => onPromote(profile.id)}
              className="flex items-center gap-1 text-xs font-medium text-brand-blue hover:text-brand-blue-dark transition-colors">
              <UserPlus size={12} /> Promote
            </button>
          )}

          {profile.status === 'promoted_pending' && (
            <span className="text-xs text-amber-600 flex items-center gap-1">
              <Clock size={10} /> Invite sent
            </span>
          )}

          <ViewCvButton submissionId={profile.parsed_submission_id} />

          {hasReasoning && (
            <button onClick={() => setExpanded(v => !v)}
              className="p-1.5 rounded-lg text-text-muted hover:text-brand-blue hover:bg-brand-blue/5 transition-colors"
              aria-expanded={expanded}>
              <Brain size={14} />
            </button>
          )}
        </div>
      </div>

      {/* AI reasoning panel */}
      {expanded && hasReasoning && (
        <div className="border-t border-border bg-gradient-to-b from-surface-muted to-white px-5 py-4 space-y-3">
          {profile.ai_fit_summary && (
            <p className="text-sm text-text leading-relaxed">{profile.ai_fit_summary}</p>
          )}
          <div className="grid sm:grid-cols-2 gap-3">
            {profile.ai_strengths?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-1.5">Strengths</p>
                <ul className="space-y-1">
                  {profile.ai_strengths.map((s, i) => (
                    <li key={i} className="text-xs text-text flex items-start gap-1.5">
                      <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>{s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {profile.ai_weaknesses?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1.5">Considerations</p>
                <ul className="space-y-1">
                  {profile.ai_weaknesses.map((w, i) => (
                    <li key={i} className="text-xs text-text flex items-start gap-1.5">
                      <span className="text-amber-500 mt-0.5 flex-shrink-0">·</span>{w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Pipeline Row (no-job pipeline view) ─────────────────────────────────────

function PipelineRow({ profile, isAdmin, onPromote, onStatusChange }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-white hover:border-brand-blue/20 hover:shadow-sm transition-all group">
      <div className="w-8 h-8 rounded-full bg-surface-muted flex items-center justify-center flex-shrink-0">
        <Users size={14} className="text-text-muted" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text truncate">
          {profile.candidate_name ?? profile.candidate_email ?? `Unidentified · ${profile.id.slice(0, 8)}`}
        </p>
        <p className="text-xs text-text-muted flex items-center gap-1.5 mt-0.5">
          <span>{SOURCE_ICONS[profile.source]}</span>
          <span className="capitalize">{profile.source}</span>
          {profile.candidate_current_title && <><span className="text-border">·</span><span>{profile.candidate_current_title}</span></>}
        </p>
      </div>

      {/* Unscored indicator */}
      {profile.ai_score == null && (
        <span className="text-xs text-text-muted bg-surface-muted px-2 py-0.5 rounded-full border border-border">
          Unscored
        </span>
      )}

      <StatusBadge status={profile.status} />

      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        {!['promoted', 'promoted_pending'].includes(profile.status) && (
          <div className="relative">
            <select value="" onChange={e => { if (e.target.value) onStatusChange(profile.id, e.target.value) }}
              className="appearance-none text-xs rounded-lg border border-border bg-white pl-2.5 pr-7 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-blue cursor-pointer">
              <option value="" disabled>Move to…</option>
              {STATUSES.filter(s => s !== profile.status && !['promoted', 'promoted_pending'].includes(s)).map(s => (
                <option key={s} value={s}>{STATUS_CONFIG[s]?.label ?? s}</option>
              ))}
            </select>
            <ChevronDown size={10} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted" />
          </div>
        )}
        {isAdmin && profile.status === 'shortlisted' && (
          <button onClick={() => onPromote(profile.id)}
            className="text-xs font-medium text-brand-blue hover:underline flex items-center gap-1">
            <UserPlus size={11} /> Promote
          </button>
        )}
        <ViewCvButton submissionId={profile.parsed_submission_id} />
      </div>
    </div>
  )
}

// ─── Promote Modal ────────────────────────────────────────────────────────────

function PromoteModal({ profileId, onClose, onDone }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handlePromote = async () => {
    setLoading(true)
    try {
      const { data } = await api.post(`/api/v1/talent-pool/${profileId}/promote`)
      setResult(data)
      if (data.status === 'invite_sent') onDone()
    } catch (err) {
      setResult({ status: 'error', message: err.response?.data?.detail ?? 'Promotion failed.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="w-12 h-12 rounded-xl bg-brand-blue/10 flex items-center justify-center mx-auto">
          <UserPlus size={22} className="text-brand-blue" />
        </div>
        <div className="text-center">
          <h3 className="font-semibold text-text text-base">Promote to Candidate</h3>
          <p className="text-sm text-text-muted mt-1">An invite email will be sent. The application is only created after they confirm.</p>
        </div>

        {!result ? (
          <div className="flex gap-2 pt-2">
            <Button variant="outline" onClick={onClose} className="flex-1">Cancel</Button>
            <Button onClick={handlePromote} disabled={loading} className="flex-1">
              {loading ? 'Sending…' : 'Send Invite'}
            </Button>
          </div>
        ) : result.status === 'invite_sent' ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-3 py-2.5 text-sm text-green-700">
              <CheckCircle2 size={16} /> Invite sent successfully.
            </div>
            <Button className="w-full" onClick={onClose}>Done</Button>
          </div>
        ) : result.status === 'conflict' ? (
          <div className="space-y-3">
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2.5 text-sm text-amber-800">
              <strong>{result.conflict_email}</strong> already has an active account. Manual review required.
            </div>
            <Button variant="outline" className="w-full" onClick={onClose}>Close</Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">{result.message}</div>
            <Button variant="outline" className="w-full" onClick={onClose}>Close</Button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Stats Bar ────────────────────────────────────────────────────────────────

function StatsBar({ profiles }) {
  const total = profiles.length
  const scored = profiles.filter(p => p.ai_score != null).length
  const shortlisted = profiles.filter(p => p.status === 'shortlisted').length
  const avgScore = scored > 0
    ? Math.round(profiles.filter(p => p.ai_score != null).reduce((s, p) => s + p.ai_score, 0) / scored)
    : null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: 'Total profiles', value: total, icon: Users, color: 'text-brand-blue' },
        { label: 'Scored', value: scored, icon: BarChart3, color: 'text-green-600' },
        { label: 'Shortlisted', value: shortlisted, icon: Star, color: 'text-amber-600' },
        { label: 'Avg. AI score', value: avgScore != null ? `${avgScore}` : '—', icon: Brain, color: 'text-purple-600' },
      ].map(({ label, value, icon: Icon, color }) => (
        <div key={label} className="rounded-xl border border-border bg-white px-4 py-3 flex items-center gap-3">
          <div className={cn('w-8 h-8 rounded-lg bg-current/10 flex items-center justify-center flex-shrink-0', color.replace('text-', 'bg-').replace('600', '100').replace('blue', 'blue/10'))}>
            <Icon size={16} className={color} />
          </div>
          <div>
            <p className="text-lg font-bold text-text leading-none">{value}</p>
            <p className="text-xs text-text-muted mt-0.5">{label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function TalentPoolPage() {
  const { user } = useAuth()
  const { show, ToastContainer } = useToast()
  const isAdmin = user?.role === 'ADMIN'

  const [profiles, setProfiles] = useState([])
  const [cursor, setCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [jobs, setJobs] = useState([])

  // Filters
  const [activeJob, setActiveJob] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [search, setSearch] = useState('')

  // UI state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [promoteId, setPromoteId] = useState(null)
  const [scoring, setScoring] = useState(false)

  const mode = activeJob ? 'job' : 'pipeline'

  const loadProfiles = useCallback(async (reset = true) => {
    setLoading(true)
    try {
      const params = { limit: 50 }
      if (statusFilter) params.status = statusFilter
      if (sourceFilter) params.source = sourceFilter
      if (activeJob) params.job_id = activeJob
      if (!reset && cursor) params.cursor = cursor
      const { data } = await api.get('/api/v1/talent-pool', { params })
      const items = data.items ?? []
      setProfiles(prev => reset ? items : [...prev, ...items])
      setCursor(data.next_cursor ?? null)
    } catch {
      show('Failed to load talent pool', 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, sourceFilter, activeJob, cursor])

  useEffect(() => { loadProfiles(true) }, [statusFilter, sourceFilter, activeJob])

  useEffect(() => {
    api.get('/api/v1/jobs/mine', { params: { limit: 100 } })
      .then(({ data }) => setJobs(data.items ?? []))
      .catch(() => {})
  }, [])

  const handleStatusChange = async (profileId, newStatus) => {
    try {
      await api.patch(`/api/v1/talent-pool/${profileId}/status`, { status: newStatus })
      setProfiles(prev => prev.map(p => p.id === profileId ? { ...p, status: newStatus } : p))
    } catch { show('Failed to update status', 'error') }
  }

  const handleScoreAgainstJob = async () => {
    if (!activeJob) return
    setScoring(true)
    try {
      const { data } = await api.post(`/api/v1/talent-pool/score-against-job?job_id=${activeJob}`)
      show(`Queued scoring for ${data.queued} profile${data.queued !== 1 ? 's' : ''}. Results will appear shortly.`, 'success')
      setTimeout(() => loadProfiles(true), 3000)
    } catch { show('Failed to trigger scoring', 'error') }
    finally { setScoring(false) }
  }

  // Client-side search filter
  const filtered = profiles.filter(p => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (p.candidate_name ?? '').toLowerCase().includes(q) ||
      p.source.toLowerCase().includes(q) ||
      (p.source_note ?? '').toLowerCase().includes(q)
    )
  })

  const activeJobTitle = jobs.find(j => j.id === activeJob)?.title

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <ToastContainer />

      <main className="flex-1 pt-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 space-y-6">

          {/* Page header */}
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-brand-blue uppercase tracking-widest mb-1">Recruitment Intelligence</p>
              <h1 className="text-2xl font-bold text-text">Talent Pool</h1>
              <p className="text-sm text-text-muted mt-1">
                {mode === 'job'
                  ? `Showing candidates ranked against ${activeJobTitle ?? 'selected job'}`
                  : 'Browse your talent pipeline — select a job to see AI rankings'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {mode === 'job' && (
                <Button variant="outline" size="sm" onClick={handleScoreAgainstJob} disabled={scoring}
                  className="flex items-center gap-1.5">
                  <Zap size={13} className={scoring ? 'animate-pulse' : ''} />
                  {scoring ? 'Scoring…' : 'Score all'}
                </Button>
              )}
              <Button onClick={() => setDrawerOpen(true)} size="sm" className="flex items-center gap-1.5">
                <Upload size={13} /> Add CV
              </Button>
            </div>
          </div>

          {/* Job selector — the primary control */}
          <div className="rounded-xl border border-border bg-white p-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <div className="flex items-center gap-2 flex-shrink-0">
                <Briefcase size={16} className="text-brand-blue" />
                <span className="text-sm font-medium text-text">View against job:</span>
              </div>
              <div className="relative flex-1 max-w-sm">
                <select value={activeJob} onChange={e => setActiveJob(e.target.value)}
                  className="w-full text-sm rounded-lg border border-border px-3 py-2 pr-8 appearance-none focus:outline-none focus:ring-2 focus:ring-brand-blue bg-white">
                  <option value="">Pipeline view (no job selected)</option>
                  {jobs.map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
              </div>
              {mode === 'job' && (
                <span className="text-xs text-brand-blue bg-brand-blue/10 px-2.5 py-1 rounded-full font-medium flex items-center gap-1">
                  <TrendingUp size={11} /> Ranked by AI score
                </span>
              )}
              {mode === 'pipeline' && (
                <span className="text-xs text-text-muted bg-surface-muted px-2.5 py-1 rounded-full border border-border">
                  Select a job to enable AI ranking
                </span>
              )}
            </div>
          </div>

          {/* Stats */}
          {profiles.length > 0 && <StatsBar profiles={profiles} />}

          {/* Filters + search */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[200px] max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search profiles…"
                className="w-full text-sm rounded-lg border border-border pl-9 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue" />
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <Filter size={14} className="text-text-muted" />
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
                className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue">
                <option value="">All statuses</option>
                {STATUSES.map(s => <option key={s} value={s}>{STATUS_CONFIG[s]?.label ?? s}</option>)}
              </select>
              <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}
                className="text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue">
                <option value="">All sources</option>
                {SOURCES.map(s => <option key={s} value={s}>{SOURCE_ICONS[s]} {s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
              </select>
              <button onClick={() => loadProfiles(true)} aria-label="Refresh"
                className="p-2 rounded-lg border border-border text-text-muted hover:bg-white hover:text-text transition-colors">
                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* Content */}
          {loading && profiles.length === 0 ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-20 rounded-xl bg-white border border-border animate-pulse" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-20 rounded-xl border border-dashed border-border bg-white">
              <div className="w-14 h-14 rounded-xl bg-surface-muted flex items-center justify-center mx-auto mb-3">
                <Users size={24} className="text-text-muted" />
              </div>
              <p className="font-semibold text-text mb-1">No profiles found</p>
              <p className="text-sm text-text-muted mb-4">
                {mode === 'job'
                  ? 'Upload CVs with this job attached, or click "Score all" to rank existing pipeline profiles.'
                  : 'Start building your pipeline by uploading a CV.'}
              </p>
              <Button size="sm" onClick={() => setDrawerOpen(true)}>
                <Upload size={13} className="mr-1.5" /> Add first CV
              </Button>
            </div>
          ) : mode === 'job' ? (
            <div className="space-y-3">
              {filtered.map((p, i) => (
                <CandidateCard
                  key={p.id}
                  profile={p}
                  rank={i + 1}
                  isAdmin={isAdmin}
                  onPromote={setPromoteId}
                  onStatusChange={handleStatusChange}
                />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map(p => (
                <PipelineRow
                  key={p.id}
                  profile={p}
                  isAdmin={isAdmin}
                  onPromote={setPromoteId}
                  onStatusChange={handleStatusChange}
                />
              ))}
            </div>
          )}

          {/* Load more */}
          {cursor && (
            <div className="flex justify-center pt-2">
              <Button variant="outline" onClick={() => loadProfiles(false)} disabled={loading}>
                {loading ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}
        </div>
      </main>

      <UploadDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onUploaded={() => loadProfiles(true)}
        jobs={jobs}
      />

      {promoteId && (
        <PromoteModal
          profileId={promoteId}
          onClose={() => setPromoteId(null)}
          onDone={() => { setPromoteId(null); loadProfiles(true) }}
        />
      )}

      <Footer />
    </div>
  )
}
