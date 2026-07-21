import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck, FileText, Trash2, ExternalLink, Loader2 } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import StatusBadge from '@/components/admin/StatusBadge'
import { KycDocumentUpload } from '@/components/employer/KycDocumentUpload'
import { Button } from '@/components/ui/button'
import { useEmployerKyc } from '@/hooks/useEmployerKyc'
import { useAuth } from '@/context/AuthContext'

/**
 * CompanyVerificationPage — /employer/verification
 * Company Verification (KYC) step. Employers upload verification documents
 * here and submit them for admin review before they can post jobs.
 */
export default function CompanyVerificationPage() {
  const { updateUser } = useAuth()
  const {
    getKycStatus,
    uploadKycDocument,
    deleteKycDocument,
    getKycDocumentUrl,
    submitKyc,
  } = useEmployerKyc()

  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const data = await getKycStatus()
      setStatus(data)
      updateUser({ kyc_status: data.kyc_status })
    } catch {
      setLoadError('Could not load verification status.')
    }
  }, [getKycStatus, updateUser])

  useEffect(() => {
    refresh().finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleUpload(file, documentType) {
    setActionError(null)
    await uploadKycDocument(file, documentType)
    await refresh()
  }

  async function handleDelete(documentId) {
    setActionError(null)
    setDeletingId(documentId)
    try {
      await deleteKycDocument(documentId)
      await refresh()
    } catch (err) {
      setActionError(err.response?.data?.message ?? 'Could not delete document.')
    } finally {
      setDeletingId(null)
    }
  }

  async function handleView(documentId) {
    try {
      const url = await getKycDocumentUrl(documentId)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      setActionError(err.response?.data?.message ?? 'Could not open document.')
    }
  }

  async function handleSubmit() {
    setActionError(null)
    setSubmitting(true)
    try {
      const data = await submitKyc()
      setStatus(data)
      updateUser({ kyc_status: data.kyc_status })
    } catch (err) {
      setActionError(err.response?.data?.message ?? 'Could not submit for verification.')
    } finally {
      setSubmitting(false)
    }
  }

  const kycStatus = status?.kyc_status ?? 'NOT_SUBMITTED'
  const canEdit = kycStatus === 'NOT_SUBMITTED' || kycStatus === 'REJECTED'
  const documents = status?.documents ?? []

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
          <div className="flex items-center gap-3 mb-8">
            <span className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-blue text-white flex-shrink-0">
              <ShieldCheck size={20} />
            </span>
            <div>
              <h1 className="text-xl font-bold text-text">Company Verification</h1>
              <p className="text-sm text-text-muted mt-0.5">
                Verify your company to unlock job posting.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16 text-text-muted">
              <Loader2 size={20} className="animate-spin" />
            </div>
          ) : loadError ? (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {loadError}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-border p-6 sm:p-8 shadow-sm space-y-6">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">Verification status</span>
                <StatusBadge value={kycStatus} />
              </div>

              {kycStatus === 'APPROVED' && (
                <div className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
                  <p className="font-medium">Your company is verified.</p>
                  <p className="mt-1">
                    You can now post jobs.{' '}
                    <Link to="/employer/jobs" className="underline font-medium">
                      Go to jobs →
                    </Link>
                  </p>
                </div>
              )}

              {kycStatus === 'PENDING' && (
                <div className="rounded-md bg-brand-amber/10 border border-brand-amber px-4 py-3 text-sm text-amber-800">
                  Your documents are under review. We&apos;ll notify you once verification is
                  complete.
                </div>
              )}

              {kycStatus === 'REJECTED' && status?.kyc_rejection_reason && (
                <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  <p className="font-medium">Verification was rejected.</p>
                  <p className="mt-1">{status.kyc_rejection_reason}</p>
                  <p className="mt-1 text-red-600">
                    Please review the reason above, update your documents, and resubmit.
                  </p>
                </div>
              )}

              {documents.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-text">Uploaded documents</p>
                  <ul className="space-y-2">
                    {documents.map((doc) => (
                      <li
                        key={doc.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText size={16} className="text-brand-blue flex-shrink-0" aria-hidden="true" />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-text truncate">{doc.filename}</p>
                            <p className="text-xs text-text-muted">{doc.document_type}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button
                            type="button"
                            onClick={() => handleView(doc.id)}
                            aria-label={`View ${doc.filename}`}
                            className="p-1.5 rounded text-text-muted hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
                          >
                            <ExternalLink size={14} aria-hidden="true" />
                          </button>
                          {canEdit && (
                            <button
                              type="button"
                              onClick={() => handleDelete(doc.id)}
                              disabled={deletingId === doc.id}
                              aria-label={`Delete ${doc.filename}`}
                              className="p-1.5 rounded text-text-muted hover:text-red-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:opacity-50"
                            >
                              <Trash2 size={14} aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {canEdit && (
                <div className="space-y-4">
                  <p className="text-sm font-medium text-text">
                    Upload a business registration certificate, tax ID, or proof of address
                  </p>
                  <KycDocumentUpload onUpload={handleUpload} />
                </div>
              )}

              {actionError && (
                <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  {actionError}
                </div>
              )}

              {canEdit && (
                <Button
                  onClick={handleSubmit}
                  disabled={documents.length === 0 || submitting}
                  className="w-full"
                  size="lg"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="mr-2 animate-spin" /> Submitting…
                    </>
                  ) : (
                    'Submit for verification'
                  )}
                </Button>
              )}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
