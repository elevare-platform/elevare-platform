import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import InterviewFlow from '@/components/candidate/InterviewFlow'
import StrictInterviewFlow from '@/components/candidate/StrictInterviewFlow'
import api from '@/lib/api'

export default function InterviewSessionPage() {
  const { applicationId } = useParams()
  const navigate = useNavigate()
  const [interview, setInterview] = useState(null)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.get(`/api/v1/interviews/applications/${applicationId}`)
      .then(({ data }) => { if (!cancelled) setInterview(data) })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err?.response?.data?.message || 'This interview is not available.')
      })
    return () => { cancelled = true }
  }, [applicationId])

  const startSession = useCallback(async () => {
    const { data } = await api.post(`/api/v1/interviews/applications/${applicationId}/session`)
    return data
  }, [applicationId])

  const requestUploadUrl = useCallback(async () => {
    const { data } = await api.post(`/api/v1/interviews/applications/${applicationId}/upload-url`)
    return data
  }, [applicationId])

  const completeUpload = useCallback(async ({ transcript, realtimeUsage }) => {
    await api.post(`/api/v1/interviews/applications/${applicationId}/complete`, {
      transcript,
      realtime_usage: realtimeUsage,
    })
  }, [applicationId])

  const requestReset = useCallback(async () => {
    const { data } = await api.post(`/api/v1/interviews/applications/${applicationId}/request-reset`)
    return data
  }, [applicationId])

  // The strict interview: start (or resume), send a spoken answer, and finish the same way.
  const startStrict = useCallback(async ({ accepted, rulesVersion }) => {
    const { data } = await api.post(`/api/v1/interviews/applications/${applicationId}/strict/start`, {
      accepted,
      rules_version: rulesVersion,
    })
    return data
  }, [applicationId])

  const sendStrictAnswer = useCallback(async (turnId, audio) => {
    const { data } = await api.post(`/api/v1/interviews/applications/${applicationId}/strict/answer`, audio, {
      params: { turn_id: turnId },
      headers: { 'Content-Type': audio.type || 'audio/webm' },
      timeout: 90_000,
    })
    return data
  }, [applicationId])

  // Where to send a recording the browser kept across a reload (the server joins the parts).
  const requestPartUploadUrl = useCallback(async () => {
    const { data } = await api.post(`/api/v1/interviews/applications/${applicationId}/strict/recording-part`)
    return data
  }, [applicationId])

  const completeStrict = useCallback(async () => {
    await api.post(`/api/v1/interviews/applications/${applicationId}/complete`, {})
  }, [applicationId])

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

  if (!interview) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center px-4 py-10">
        <div className="w-8 h-8 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </main>
    )
  }

  if (interview.style === 'strict') {
    return (
      <StrictInterviewFlow
        startInterview={startStrict}
        sendAnswer={sendStrictAnswer}
        requestUploadUrl={requestUploadUrl}
        completeUpload={completeStrict}
        requestPartUploadUrl={requestPartUploadUrl}
        backTo="/candidate/applications"
        backLabel="Back to applications"
        doneAction={{
          label: 'Back to applications',
          onClick: () => navigate('/candidate/applications'),
        }}
        resuming={interview.status === 'IN_PROGRESS'}
        completed={['UPLOADED', 'SCORED'].includes(interview.status)}
      />
    )
  }

  return (
    <InterviewFlow
      startSession={startSession}
      requestUploadUrl={requestUploadUrl}
      completeUpload={completeUpload}
      requestReset={requestReset}
      backTo="/candidate/applications"
      backLabel="Back to applications"
      doneAction={{
        label: 'Back to applications',
        onClick: () => navigate('/candidate/applications'),
      }}
      sessionStartCount={interview.session_start_count}
    />
  )
}
