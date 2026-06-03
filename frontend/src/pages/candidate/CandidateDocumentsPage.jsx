import { useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, AlertCircle, RefreshCw } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { CvSection } from '@/components/candidate/CvSection'
import { CvUpload } from '@/components/candidate/CvUpload'
import { DocumentsSection } from '@/components/candidate/DocumentsSection'
import { DocumentUpload } from '@/components/candidate/DocumentUpload'
import { useCandidateProfile } from '@/hooks/useCandidateProfile'
import api from '@/lib/api'

function ToastError({ message, onDismiss }) {
  if (!message) return null
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <span className="flex items-center gap-2"><AlertCircle size={15} />{message}</span>
      <button type="button" onClick={onDismiss} className="text-red-500 hover:text-red-700 text-xs underline">Dismiss</button>
    </div>
  )
}

export default function CandidateDocumentsPage() {
  const { profile, loading, error, refetch, setCvs, setDocuments } = useCandidateProfile()
  const cvUploadRef = useRef(null)
  const [actionError, setActionError] = useState(null)

  const handleCvDownload = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/api/v1/candidates/me/cv/${id}/url`)
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (err) { setActionError(err?.response?.data?.detail ?? 'Failed to get download URL.') }
  }, [])

  const handleCvSetDefault = useCallback(async (id) => {
    setCvs((prev) => prev.map((cv) => ({ ...cv, is_default: cv.id === id })))
    try { await api.put(`/api/v1/candidates/me/cv/${id}/default`) }
    catch (err) { refetch(); setActionError(err?.response?.data?.detail ?? 'Failed to set default CV.') }
  }, [setCvs, refetch])

  const handleCvDelete = useCallback(async (id) => {
    setCvs((prev) => prev.filter((cv) => cv.id !== id))
    try { await api.delete(`/api/v1/candidates/me/cv/${id}`) }
    catch (err) { refetch(); setActionError(err?.response?.data?.detail ?? 'Failed to delete CV.') }
  }, [setCvs, refetch])

  const handleCvUploadSuccess = useCallback((newCv) => {
    setCvs((prev) => [...prev, newCv])
  }, [setCvs])

  const handleDocDownload = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/api/v1/candidates/me/documents/${id}/url`)
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (err) { setActionError(err?.response?.data?.detail ?? 'Failed to get download URL.') }
  }, [])

  const handleDocDelete = useCallback(async (id) => {
    setDocuments((prev) => prev.filter((doc) => doc.id !== id))
    try { await api.delete(`/api/v1/candidates/me/documents/${id}`) }
    catch (err) { refetch(); setActionError(err?.response?.data?.detail ?? 'Failed to delete document.') }
  }, [setDocuments, refetch])

  const handleDocUploadSuccess = useCallback((newDoc) => {
    setDocuments((prev) => [...prev, newDoc])
  }, [setDocuments])

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <main className="flex-1 pt-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-8">

          <Link to="/candidate/dashboard" className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-brand-blue transition-colors">
            <ArrowLeft size={14} /> Back to Dashboard
          </Link>

          <div>
            <h1 className="text-2xl font-bold text-text">My Documents</h1>
            <p className="text-text-muted text-sm mt-1">Manage your CVs and supporting documents.</p>
          </div>

          {loading && (
            <div className="space-y-4 animate-pulse">
              {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-gray-200 rounded-lg" />)}
            </div>
          )}

          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 flex flex-col items-center gap-4 text-center">
              <AlertCircle size={32} className="text-red-400" />
              <p className="font-semibold text-red-700">Failed to load documents</p>
              <button type="button" onClick={refetch} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50">
                <RefreshCw size={14} /> Retry
              </button>
            </div>
          )}

          {actionError && <ToastError message={actionError} onDismiss={() => setActionError(null)} />}

          {!loading && !error && profile && (
            <>
              <section className="bg-white rounded-xl border border-border p-6 space-y-4">
                <CvSection
                  cvs={profile.cvs ?? []}
                  onDownload={handleCvDownload}
                  onSetDefault={handleCvSetDefault}
                  onDelete={handleCvDelete}
                  uploadRef={cvUploadRef}
                />
                <div ref={cvUploadRef}>
                  <CvUpload onUploadSuccess={handleCvUploadSuccess} />
                </div>
              </section>

              <section className="bg-white rounded-xl border border-border p-6 space-y-4">
                <DocumentsSection
                  documents={profile.documents ?? []}
                  onDownload={handleDocDownload}
                  onDelete={handleDocDelete}
                />
                <DocumentUpload onUploadSuccess={handleDocUploadSuccess} />
              </section>
            </>
          )}

        </div>
      </main>
      <Footer />
    </div>
  )
}
