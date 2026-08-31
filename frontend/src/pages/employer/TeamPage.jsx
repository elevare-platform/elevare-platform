import { useEffect, useState, useCallback } from 'react'
import { Users, UserPlus, Trash2, Loader2, Copy, Check } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { useTeam } from '@/hooks/useTeam'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

// ─── Invite link card (stub-mode convenience — production sends the email directly) ──

function InviteLinkCard({ email, token }) {
  const [copied, setCopied] = useState(false)
  const inviteUrl = `${window.location.origin}/invite/accept?token=${token}`

  const handleCopy = async () => {
    await navigator.clipboard.writeText(inviteUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-green-800">Invite created</p>
          <p className="text-xs text-green-700 mt-0.5">
            Invite link for <span className="font-medium">{email}</span>
          </p>
        </div>
        <span className="flex-shrink-0 w-7 h-7 rounded-full bg-green-200 flex items-center justify-center">
          <Check size={14} className="text-green-700" />
        </span>
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 min-w-0 block text-xs bg-white border border-green-200 rounded-lg px-3 py-2 text-green-900 truncate font-mono">
          {inviteUrl}
        </code>
        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            'flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors',
            copied
              ? 'bg-green-600 text-white'
              : 'bg-white border border-green-200 text-green-700 hover:bg-green-100'
          )}
          aria-label="Copy invite link"
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

/**
 * TeamPage - /employer/team
 * Lets an organization's OWNER/ADMIN members invite and remove teammates.
 * Any member can view the list; invite/remove are gated by organization_role.
 */
export default function TeamPage() {
  const { user } = useAuth()
  const canManage = user?.organization_role === 'OWNER' || user?.organization_role === 'ADMIN'

  const { listMembers, inviteMember, removeMember, loading } = useTeam()

  const [members, setMembers] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [email, setEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState(null)
  const [sentInvites, setSentInvites] = useState([])
  const [inviteSentMessage, setInviteSentMessage] = useState(null)
  const [removingId, setRemovingId] = useState(null)
  const [removeError, setRemoveError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const data = await listMembers()
      setMembers(data)
    } catch {
      setLoadError('Could not load your team.')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleInvite(e) {
    e.preventDefault()
    setInviteError(null)
    setInviteSentMessage(null)
    setInviting(true)
    try {
      const result = await inviteMember(email)
      // In stub mode (no real email provider configured) the response
      // includes the raw token so it can be copied and shared manually.
      // In production the invite email has already been sent — just
      // confirm it went out, nothing to copy.
      const token = result?.data?.invite_token
      if (token) {
        setSentInvites((prev) => [{ email, token }, ...prev])
      } else {
        setInviteSentMessage(`Invite sent to ${email}.`)
      }
      setEmail('')
    } catch (err) {
      setInviteError(err.response?.data?.message ?? 'Could not send invite.')
    } finally {
      setInviting(false)
    }
  }

  async function handleRemove(userId) {
    setRemoveError(null)
    setRemovingId(userId)
    try {
      await removeMember(userId)
      await refresh()
    } catch (err) {
      setRemoveError(err.response?.data?.message ?? 'Could not remove teammate.')
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />

      <main className="flex-1 pt-16">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
          <div className="flex items-center gap-3 mb-8">
            <span className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-blue text-white flex-shrink-0">
              <Users size={20} />
            </span>
            <div>
              <h1 className="text-xl font-bold text-text">Team</h1>
              <p className="text-sm text-text-muted mt-0.5">
                Everyone at your company sharing this account.
              </p>
            </div>
          </div>

          {loading && members.length === 0 ? (
            <div className="flex items-center justify-center py-16 text-text-muted">
              <Loader2 size={20} className="animate-spin" />
            </div>
          ) : loadError ? (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {loadError}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-border p-6 sm:p-8 shadow-sm space-y-6">
              <ul className="space-y-2">
                {members.map((member) => (
                  <li
                    key={member.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text truncate">
                        {member.first_name} {member.last_name}
                        {member.id === user?.id && (
                          <span className="text-text-muted font-normal"> (you)</span>
                        )}
                      </p>
                      <p className="text-xs text-text-muted truncate">{member.email}</p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-brand-blue">
                        {member.organization_role}
                      </span>
                      {canManage && member.id !== user?.id && (
                        <button
                          type="button"
                          onClick={() => handleRemove(member.id)}
                          disabled={removingId === member.id}
                          aria-label={`Remove ${member.first_name} ${member.last_name}`}
                          className="p-1.5 rounded text-text-muted hover:text-red-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:opacity-50"
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>

              {removeError && (
                <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  {removeError}
                </div>
              )}

              {canManage && (
                <form onSubmit={handleInvite} className="space-y-3 pt-2 border-t border-border">
                  <p className="text-sm font-medium text-text pt-4">Invite a teammate</p>
                  <div className="flex gap-2">
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="teammate@company.com"
                      className="flex-1 rounded-md border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
                    />
                    <Button type="submit" disabled={inviting}>
                      {inviting ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <>
                          <UserPlus size={16} className="mr-2" /> Invite
                        </>
                      )}
                    </Button>
                  </div>
                  {inviteError && <p className="text-sm text-red-700">{inviteError}</p>}
                  {inviteSentMessage && (
                    <p className="text-sm text-green-700">{inviteSentMessage}</p>
                  )}
                </form>
              )}

              {sentInvites.length > 0 && (
                <div className="space-y-3">
                  {sentInvites.map((inv) => (
                    <InviteLinkCard key={inv.token} email={inv.email} token={inv.token} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}
