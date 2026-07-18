import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Mail, X, RefreshCw, ChevronDown, CheckCircle2,
  AlertCircle, Inbox, Trash2, Zap, Upload, ArrowRight
} from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { useToast } from '@/components/admin/Toast'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Constants & Helpers ──────────────────────────────────────────────────────

const INTEGRATION_STATUS = {
  CONNECTED: { label: 'Connected', dot: 'bg-green-500' },
  DISCONNECTED: { label: 'Disconnected', dot: 'bg-gray-400' },
  ERROR: { label: 'Error', dot: 'bg-red-500' },
  REVOKED: { label: 'Revoked', dot: 'bg-gray-400' },
}

const RUN_STATUS_COLORS = {
  PENDING: 'bg-amber-100 text-amber-700 border-amber-200',
  RUNNING: 'bg-blue-100 text-blue-700 border-blue-200',
  COMPLETED: 'bg-green-100 text-green-700 border-green-200',
  FAILED: 'bg-red-100 text-red-700 border-red-200',
  CANCELLED: 'bg-gray-100 text-gray-700 border-gray-200',
  PAUSED: 'bg-amber-100 text-amber-700 border-amber-200',
}

function IntegrationStatusDot({ status }) {
  const cfg = INTEGRATION_STATUS[status] || INTEGRATION_STATUS.DISCONNECTED
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn('w-2 h-2 rounded-full', cfg.dot)} />
      <span className="text-xs font-medium text-text-muted">{cfg.label}</span>
    </div>
  )
}

function RunStatusBadge({ status }) {
  const color = RUN_STATUS_COLORS[status] || 'bg-gray-100 text-gray-700 border-gray-200'
  return (
    <span className={cn('inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border', color)}>
      {status}
    </span>
  )
}

function progressPercent(run) {
  if (!run) return 0
  if (run.status === 'COMPLETED') return 100
  if (!run.total_emails_found) return 0
  return Math.round(((run.emails_processed + run.emails_skipped) / run.total_emails_found) * 100)
}

function relativeTime(isoString) {
  if (!isoString) return ''
  const diffMs = Date.now() - new Date(isoString).getTime()
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

// ─── ImportRunCard ────────────────────────────────────────────────────────────

function ImportRunCard({ integrationId, initialRunId, onComplete }) {
  const [run, setRun] = useState(null)
  const timerRef = useRef(null)

  const fetchRun = useCallback(async () => {
    if (!initialRunId || !integrationId) return
    try {
      const { data } = await api.get(`/api/v1/ingestion/integrations/${integrationId}/runs/${initialRunId}`)
      setRun(data)
      if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(data.status)) {
        clearInterval(timerRef.current)
        if (onComplete) onComplete()
      }
    } catch (err) {
      // Ignore poll errors
    }
  }, [integrationId, initialRunId, onComplete])

  useEffect(() => {
    if (!initialRunId) return
    fetchRun()
    timerRef.current = setInterval(fetchRun, 2500)
    return () => clearInterval(timerRef.current)
  }, [initialRunId, fetchRun])

  if (!run) return null

  const isRunning = ['PENDING', 'RUNNING'].includes(run.status)
  const pct = progressPercent(run)

  return (
    <div className="rounded-lg border border-border bg-white p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RunStatusBadge status={run.status} />
          <span className="text-xs text-text-muted">
            {new Date(run.created_at).toLocaleString()}
          </span>
        </div>
        {isRunning && <RefreshCw size={14} className="text-brand-blue animate-spin" />}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="rounded border border-border bg-surface-muted p-2 text-center">
          <p className="text-xl font-bold text-text leading-none">{run.total_emails_found}</p>
          <p className="text-[10px] text-text-muted uppercase font-semibold mt-1">Found</p>
        </div>
        <div className="rounded border border-border bg-surface-muted p-2 text-center">
          <p className="text-xl font-bold text-brand-blue leading-none">{run.emails_processed}</p>
          <p className="text-[10px] text-text-muted uppercase font-semibold mt-1">Processed</p>
        </div>
        <div className="rounded border border-border bg-surface-muted p-2 text-center">
          <p className="text-xl font-bold text-amber-600 leading-none">{run.emails_deduplicated}</p>
          <p className="text-[10px] text-text-muted uppercase font-semibold mt-1">Duplicate</p>
        </div>
        <div className="rounded border border-border bg-surface-muted p-2 text-center">
          <p className="text-xl font-bold text-gray-500 leading-none">{run.emails_skipped}</p>
          <p className="text-[10px] text-text-muted uppercase font-semibold mt-1">Skipped</p>
        </div>
      </div>

      {run.error_message && (
        <div className="flex items-start gap-1.5 p-2 rounded bg-red-50 text-red-700 text-xs border border-red-200">
          <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
          <span>{run.error_message}</span>
        </div>
      )}

      {(isRunning || run.status === 'COMPLETED') && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[10px] font-semibold text-text-muted uppercase">
            <span>Progress</span>
            <span>{pct}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-surface-muted overflow-hidden relative">
            <div
              className={cn('absolute inset-y-0 left-0 bg-brand-blue transition-all duration-500')}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ─── TriggerImportModal (Drawer) ──────────────────────────────────────────────

function TriggerImportModal({ open, onClose, integration, initialRun, jobs, onViewTalentPool, onRunFinished }) {
  const [jobId, setJobId] = useState('')
  const [queryFilter, setQueryFilter] = useState('has:attachment')
  const [submitting, setSubmitting] = useState(false)
  const [runId, setRunId] = useState(null)
  const [completed, setCompleted] = useState(false)
  const { show } = useToast()

  // Reopening on an integration with an active run (e.g. after navigating
  // away and back) should show live progress immediately, not the "start
  // a new import" form — the backend would reject a second run anyway.
  useEffect(() => {
    if (!open) return
    if (initialRun && ['RUNNING', 'PENDING'].includes(initialRun.status)) {
      setRunId(initialRun.id)
    }
  }, [open, initialRun])

  const reset = () => {
    setJobId('')
    setQueryFilter('has:attachment')
    setRunId(null)
    setCompleted(false)
  }

  const handleSubmit = async () => {
    if (!integration) return
    setSubmitting(true)
    try {
      const payload = {}
      if (queryFilter) payload.query_filter = queryFilter
      if (jobId) payload.sourced_for_job_id = jobId
      const { data } = await api.post(`/api/v1/ingestion/integrations/${integration.id}/import`, payload)
      setRunId(data.id)
      show('Import started', 'success')
    } catch (err) {
      show(err.response?.data?.detail || 'Failed to start import', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex" onClick={() => { reset(); onClose() }}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />
      <div
        className="relative ml-auto w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl flex flex-col"
        onClick={e => e.stopPropagation()}
        role="dialog"
      >
        <div className="flex items-center justify-between px-6 py-5 border-b border-border">
          <div>
            <h2 className="font-semibold text-text text-base">Import CVs</h2>
            <p className="text-xs text-text-muted mt-0.5">From {integration?.email_address}</p>
          </div>
          <button onClick={() => { reset(); onClose() }} className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 px-6 py-6 space-y-6">
          {!runId && initialRun && (
            <div className="rounded-lg border border-border bg-surface-muted p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wide">Last import</span>
                <RunStatusBadge status={initialRun.status} />
              </div>
              <p className="text-xs text-text-muted">
                {initialRun.total_emails_found} found · {initialRun.emails_processed} processed ·{' '}
                {initialRun.emails_deduplicated} duplicate · {initialRun.emails_skipped} skipped
                {initialRun.completed_at && <> · {relativeTime(initialRun.completed_at)}</>}
              </p>
              {initialRun.error_message && (
                <p className="text-xs text-red-600">{initialRun.error_message}</p>
              )}
            </div>
          )}

          {!runId && (
            <>
              <div>
                <label className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 block">
                  Score against job <span className="normal-case font-normal">(optional)</span>
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
                    <Zap size={11} /> AI scoring runs automatically after parsing
                  </p>
                )}
              </div>

              <div>
                <label className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2 block">
                  Search query
                </label>
                <input
                  value={queryFilter}
                  onChange={e => setQueryFilter(e.target.value)}
                  placeholder="has:attachment"
                  className="w-full text-sm rounded-lg border border-border px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                />
                <p className="text-xs text-text-muted mt-1.5">
                  {integration?.provider === 'ZOHO'
                    ? 'Zoho Mail search syntax — e.g. has:attachment, after:2024-01-01, subject:CV'
                    : 'Gmail search syntax — e.g. has:attachment, after:2024/01/01, subject:CV'}
                  {' '}Leave blank to import all emails with attachments.
                </p>
              </div>
            </>
          )}

          {runId && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <RefreshCw size={14} className="text-brand-blue animate-spin" /> Import running in background
              </div>
              <ImportRunCard
                integrationId={integration?.id}
                initialRunId={runId}
                onComplete={() => { setCompleted(true); onRunFinished?.() }}
              />

              {/* CTA shown once import reaches COMPLETED */}
              {completed && (
                <div className="rounded-xl border border-green-200 bg-green-50 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-green-800">
                    <CheckCircle2 size={16} className="text-green-600" /> Import complete
                  </div>
                  <p className="text-xs text-green-700">
                    Parsed CVs are now in your Talent Pool. Parsing and AI scoring continue in the background.
                  </p>
                  <button
                    onClick={() => { reset(); onClose(); onViewTalentPool() }}
                    className="flex items-center gap-1.5 text-xs font-semibold text-green-800 hover:text-green-900 transition-colors"
                  >
                    View imported CVs in Talent Pool <ArrowRight size={13} />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-5 border-t border-border space-y-2">
          {!runId ? (
            <Button onClick={handleSubmit} disabled={submitting} className="w-full" size="lg">
              {submitting ? 'Starting...' : 'Start Import'}
            </Button>
          ) : (
            <Button onClick={() => { reset(); onClose() }} variant="outline" className="w-full" size="lg">
              Run in background — close
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Disconnect Modal ─────────────────────────────────────────────────────────

function DisconnectModal({ integration, onClose, onDisconnected }) {
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState(null)

  const handleConfirm = async () => {
    setDisconnecting(true)
    setError(null)
    try {
      await api.delete(`/api/v1/ingestion/integrations/${integration.id}`)
      onDisconnected()
    } catch {
      setError('Failed to disconnect. Please try again.')
      setDisconnecting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" aria-hidden="true" />
      <div
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-5"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Icon */}
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <Trash2 size={20} className="text-red-600" />
        </div>

        {/* Copy */}
        <div className="text-center space-y-1">
          <h3 className="font-semibold text-text text-base">
            Disconnect {integration.provider === 'ZOHO' ? 'Zoho Mail' : 'Gmail'}?
          </h3>
          <p className="text-sm text-text-muted">
            <span className="font-medium text-text">{(integration.email_address || '').split('|')[0]}</span> will be disconnected.
            Existing imported CVs stay in your Talent Pool.
          </p>
        </div>

        {error && (
          <p className="text-xs text-red-600 text-center">{error}</p>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <Button variant="outline" onClick={onClose} className="flex-1" disabled={disconnecting}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={disconnecting}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white border-0"
          >
            {disconnecting ? 'Disconnecting...' : 'Disconnect'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── IntegrationCard ──────────────────────────────────────────────────────────

function IntegrationCard({ integration, onImportClick, onDisconnectClick }) {
  const run = integration.latest_run
  const runActive = run && ['RUNNING', 'PENDING'].includes(run.status)
  const pct = runActive ? progressPercent(run) : 0

  return (
    <div className="rounded-xl border border-border bg-white p-5 flex flex-col gap-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
            integration.provider === 'ZOHO'
              ? 'bg-orange-100 text-orange-600'
              : 'bg-red-100 text-red-600'
          )}>
            <Mail size={20} />
          </div>
          <div>
            <p className="font-semibold text-text text-sm">
              {/* Show only the email part — strip the |account_id suffix Zoho stores */}
              {(integration.email_address || '').split('|')[0]}
            </p>
            <IntegrationStatusDot status={integration.status} />
          </div>
        </div>
      </div>

      <div className="text-xs text-text-muted flex justify-between items-center bg-surface-muted px-3 py-2 rounded-lg border border-border">
        <span>Last synced</span>
        <span className="font-medium text-text">
          {integration.last_synced_at
            ? new Date(integration.last_synced_at).toLocaleString()
            : 'Never'}
        </span>
      </div>

      {/* Persisted import progress/summary — survives navigating away and back,
          so the user doesn't have to keep a tab open to see it. */}
      {runActive ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-blue-700 flex items-center gap-1">
              <RefreshCw size={11} className="animate-spin" /> Import running
            </span>
            <span className="text-blue-600">{run.emails_processed}/{run.total_emails_found}</span>
          </div>
          <div className="w-full h-1 rounded-full bg-blue-100 overflow-hidden">
            <div className="h-full bg-blue-500 transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
      ) : run && (
        <div className="text-xs text-text-muted flex items-center justify-between px-3 py-1.5">
          <span className="flex items-center gap-1.5">
            <RunStatusBadge status={run.status} />
            {run.emails_processed} processed
          </span>
          {run.completed_at && <span>{relativeTime(run.completed_at)}</span>}
        </div>
      )}

      <div className="flex items-center gap-2 mt-auto pt-1">
        <Button
          onClick={() => onImportClick(integration)}
          size="sm"
          className="flex-1"
          disabled={integration.status !== 'CONNECTED'}
        >
          {runActive
            ? <><RefreshCw size={14} className="mr-1.5 animate-spin" /> View Progress</>
            : <><Upload size={14} className="mr-1.5" /> Import CVs</>}
        </Button>
        <Button
          onClick={() => onDisconnectClick(integration)}
          variant="outline"
          size="sm"
          className="text-red-600 border-border hover:bg-red-50 hover:border-red-200 hover:text-red-700"
        >
          <Trash2 size={14} />
        </Button>
      </div>
    </div>
  )
}

// ─── EmptyState ───────────────────────────────────────────────────────────────

function EmptyState({ onConnect }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center max-w-md mx-auto">
      <div className="w-20 h-20 rounded-2xl bg-brand-blue/10 flex items-center justify-center mb-6 shadow-inner">
        <Inbox size={32} className="text-brand-blue" />
      </div>
      <h2 className="text-xl font-bold text-text mb-2">No mailboxes connected</h2>
      <p className="text-sm text-text-muted mb-8 leading-relaxed">
        Connect Gmail or Zoho Mail to start importing CVs from your recruitment inbox automatically.
      </p>
      <div className="flex items-center gap-3">
        <Button onClick={onConnect('gmail')} size="lg" className="flex items-center gap-2">
          <Mail size={18} /> Connect Gmail
        </Button>
        <Button onClick={onConnect('zoho')} variant="outline" size="lg" className="flex items-center gap-2">
          <Mail size={18} /> Connect Zoho
        </Button>
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function MailIngestionPage() {
  const navigate = useNavigate()
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [jobs, setJobs] = useState([])
  const [connecting, setConnecting] = useState(null) // null | 'gmail' | 'zoho'
  const { show, ToastContainer } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedIntegration, setSelectedIntegration] = useState(null)
  const [disconnectTarget, setDisconnectTarget] = useState(null)

  const loadIntegrations = useCallback(async () => {
    try {
      const { data } = await api.get('/api/v1/ingestion/integrations')
      setIntegrations(data)
    } catch {
      // silently fail — user will see empty state
    } finally {
      setLoading(false)
    }
  }, [])  // no deps — setIntegrations is stable

  const loadJobs = useCallback(async () => {
    try {
      const { data } = await api.get('/api/v1/jobs?employer=true')
      setJobs(data.items ?? [])
    } catch {
      // jobs are optional
    }
  }, [])

  useEffect(() => {
    loadIntegrations()
    loadJobs()
  }, [loadIntegrations, loadJobs])

  // Handle redirect back from Google OAuth
  useEffect(() => {
    const connected = searchParams.get('connected')
    if (!connected) return
    // Clean the URL immediately
    setSearchParams({}, { replace: true })
    if (connected === 'success') {
      show('Mailbox connected successfully', 'success')
      loadIntegrations()
      setConnecting(null)
    } else if (connected === 'error') {
      show('Failed to connect mailbox — please try again', 'error')
      setConnecting(null)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps — intentionally run once on mount

  const pollTimerRef = useRef(null)

  const handleConnect = (provider) => async () => {
    setConnecting(provider)
    try {
      const endpoint = provider === 'zoho'
        ? '/api/v1/ingestion/connect/zoho'
        : '/api/v1/ingestion/connect/gmail'
      const { data } = await api.get(endpoint)
      window.open(data.auth_url, '_blank', 'noopener,noreferrer')

      // Poll for 30s waiting for callback to complete
      let polls = 0
      pollTimerRef.current = setInterval(async () => {
        polls++
        await loadIntegrations()
        if (polls >= 10) {
          clearInterval(pollTimerRef.current)
          setConnecting(null)
        }
      }, 3000)
    } catch {
      show(`Failed to initiate ${provider === 'zoho' ? 'Zoho' : 'Gmail'} connection`, 'error')
      setConnecting(null)
    }
  }

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [])

  const handleImportClick = (integration) => {
    setSelectedIntegration(integration)
    setDrawerOpen(true)
  }

  const handleDisconnectClick = (integration) => {
    setDisconnectTarget(integration)
  }

  const handleDisconnected = () => {
    show('Mailbox disconnected', 'success')
    setDisconnectTarget(null)
    loadIntegrations()
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <ToastContainer />
      
      <main className="flex-1 pt-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 space-y-8">
          
          {/* Page header */}
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Mail size={16} className="text-brand-blue" />
                <p className="text-xs font-semibold text-brand-blue uppercase tracking-widest">Mail Ingestion</p>
              </div>
              <h1 className="text-2xl font-bold text-text">Connected Mailboxes</h1>
              <p className="text-sm text-text-muted mt-1">
                Connect your recruitment mailbox to automatically import and parse CVs
              </p>
            </div>
            {!integrations.some(i => i.status === 'CONNECTED') && (
              <div className="flex items-center gap-2">
                <Button onClick={handleConnect('gmail')} disabled={connecting} size="sm" className="flex items-center gap-1.5">
                  <Mail size={14} /> {connecting === 'gmail' ? 'Connecting...' : 'Connect Gmail'}
                </Button>
                <Button onClick={handleConnect('zoho')} disabled={connecting} variant="outline" size="sm" className="flex items-center gap-1.5">
                  <Mail size={14} /> {connecting === 'zoho' ? 'Connecting...' : 'Connect Zoho'}
                </Button>
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex justify-center py-10">
              <RefreshCw className="animate-spin text-brand-blue" />
            </div>
          ) : integrations.length === 0 ? (
            <div className="bg-white rounded-2xl border border-border">
              <EmptyState onConnect={handleConnect} />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {integrations.map(integration => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  onImportClick={handleImportClick}
                  onDisconnectClick={handleDisconnectClick}
                />
              ))}
            </div>
          )}
        </div>
      </main>
      
      <TriggerImportModal
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setSelectedIntegration(null) }}
        integration={selectedIntegration}
        initialRun={selectedIntegration?.latest_run}
        jobs={jobs}
        onRunFinished={loadIntegrations}
        onViewTalentPool={() => navigate(
          `/employer/talent-pool?source=${selectedIntegration?.provider === 'ZOHO' ? 'zoho_import' : 'gmail_import'}`
        )}
      />

      {disconnectTarget && (
        <DisconnectModal
          integration={disconnectTarget}
          onClose={() => setDisconnectTarget(null)}
          onDisconnected={handleDisconnected}
        />
      )}
      
      <Footer />
    </div>
  )
}
