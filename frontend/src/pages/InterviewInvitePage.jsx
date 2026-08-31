import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import InterviewFlow from '@/components/candidate/InterviewFlow'
import api from '@/lib/api'

/**
 * Public, no-login entry point for an AI video interview invite email.
 * Reached from a magic link — works whether or not the candidate has an
 * Elevare account, since being added to a job's interview list (not
 * having an account) is what grants access.
 */
export default function InterviewInvitePage() {
  const { token } = useParams()
  const [info, setInfo] = useState(null)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.get(`/api/v1/public/interviews/${token}`)
      .then(({ data }) => { if (!cancelled) setInfo(data) })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err?.response?.data?.message || 'This interview link is invalid or has expired.')
      })
    return () => { cancelled = true }
  }, [token])

  const startSession = useCallback(async () => {
    const { data } = await api.post(`/api/v1/public/interviews/${token}/session`)
    return data
  }, [token])

  const requestUploadUrl = useCallback(async () => {
    const { data } = await api.post(`/api/v1/public/interviews/${token}/upload-url`)
    return data
  }, [token])

  const completeUpload = useCallback(async ({ transcript, realtimeUsage }) => {
    await api.post(`/api/v1/public/interviews/${token}/complete`, {
      transcript,
      realtime_usage: realtimeUsage,
    })
  }, [token])

  const requestReset = useCallback(async () => {
    const { data } = await api.post(`/api/v1/public/interviews/${token}/request-reset`)
    return data
  }, [token])

  if (loadError) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-xl border border-red-200 bg-red-50 p-6 text-center space-y-3">
          <AlertCircle size={32} className="text-red-600 mx-auto" />
          <p className="text-sm text-red-700">{loadError}</p>
        </div>
      </main>
    )
  }

  if (!info) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center px-4 py-10">
        <div className="w-8 h-8 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </main>
    )
  }

  const subtitle = info.company_name
    ? `${info.company_name} · ${info.job_title}`
    : info.job_title

  return (
    <InterviewFlow
      startSession={startSession}
      requestUploadUrl={requestUploadUrl}
      completeUpload={completeUpload}
      requestReset={requestReset}
      subtitle={subtitle}
      sessionStartCount={info.session_start_count}
    />
  )
}
