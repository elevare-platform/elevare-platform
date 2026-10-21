import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

const URL = '/api/v1/admin/plan-exemptions'
const PAGE_SIZE = 20

// The server applies the same limits and stays the authority.
const addSchema = z.object({
  email: z.string().trim().email('Enter a valid email address'),
  reason: z
    .string()
    .trim()
    .min(3, 'Give a reason of at least 3 characters')
    .max(500, 'At most 500 characters'),
  ends_on: z.string().optional(),
})

// The date picker gives "2026-12-31" with no time and no timezone, but the server
// wants a moment in time. Use the END of that day in the admin's own timezone, so
// "ends on 31 Dec" keeps the company covered through the whole of 31 Dec.
function endOfDay(dateText) {
  return new Date(`${dateText}T23:59:59`).toISOString()
}

function formatDate(isoText) {
  return new Date(isoText).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

// Use the server's own words when it sent any: its messages are specific
// ("No account has that email address") and a generic one would hide them.
function errorText(err, fallback) {
  const body = err?.response?.data
  const firstDetail = body?.details?.[0]?.message
  const message = firstDetail ?? body?.message
  return typeof message === 'string' ? message : fallback
}

// ─── Add a company ────────────────────────────────────────────────────────────

function AddSection({ onAdded }) {
  const [serverError, setServerError] = useState(null)
  const [notice, setNotice] = useState(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(addSchema) })

  const onSubmit = async (values) => {
    setServerError(null)
    setNotice(null)
    const body = { email: values.email, reason: values.reason }
    if (values.ends_on) body.expires_at = endOfDay(values.ends_on)
    try {
      const { data } = await api.post(URL, body)
      setNotice(`${data.company_name ?? 'The company'} now keeps Professional access.`)
      reset()
      onAdded()
    } catch (err) {
      setServerError(errorText(err, 'Something went wrong. Please try again.'))
    }
  }

  return (
    <section className="bg-white rounded-xl border border-border p-6 shadow-sm space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-text">Add a company</h2>
        <p className="text-sm text-text-muted mt-1">
          Type the email of anyone who works at the company. The whole company is added. Adding a
          company that is already on the list renews it with the new reason and date.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <FormField>
          <Label htmlFor="exempt_email">Email of a team member</Label>
          <Input id="exempt_email" type="email" {...register('email')} />
          <FormMessage>{errors.email?.message}</FormMessage>
        </FormField>
        <FormField>
          <Label htmlFor="exempt_reason">Reason</Label>
          <Input
            id="exempt_reason"
            placeholder="For example: pilot customer for the October launch"
            {...register('reason')}
          />
          <FormMessage>{errors.reason?.message}</FormMessage>
        </FormField>
        <FormField>
          <Label htmlFor="exempt_ends_on">Ends on (optional)</Label>
          <Input id="exempt_ends_on" type="date" {...register('ends_on')} />
          <p className="text-xs text-text-muted">Leave empty for no end date.</p>
        </FormField>

        {serverError && (
          <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {serverError}
          </div>
        )}
        {notice && (
          <div role="status" className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
            {notice}
          </div>
        )}

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? <><Loader2 size={15} className="mr-2 animate-spin" /> Adding…</>
            : <><Plus size={15} className="mr-2" /> Add company</>}
        </Button>
      </form>
    </section>
  )
}

// ─── The list ─────────────────────────────────────────────────────────────────

function StatusBadge({ active }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
        active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
      )}
    >
      {active ? 'Active' : 'Ended'}
    </span>
  )
}

function ExemptionList({ data, status, offset, onPage, onRetry, onRemove, removingId, actionError }) {
  if (status === 'loading') {
    return (
      <p className="flex items-center gap-2 text-sm text-text-muted">
        <Loader2 size={14} className="animate-spin" /> Loading…
      </p>
    )
  }

  if (status === 'error') {
    return (
      <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between gap-3">
        <span>The list could not be loaded.</span>
        <button type="button" onClick={onRetry} className="font-medium underline underline-offset-2">
          Try again
        </button>
      </div>
    )
  }

  if (data.items.length === 0) {
    return <p className="text-sm text-text-muted">No company is on the list yet.</p>
  }

  const from = offset + 1
  const to = offset + data.items.length

  return (
    <div className="space-y-3">
      {actionError && (
        <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {actionError}
        </div>
      )}

      {/* relative: the sr-only header label is absolutely positioned, and without this it
          sits outside the scroll box and widens the whole page on a phone. */}
      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-text-muted border-b border-border">
              <th className="py-2 pr-4 font-semibold">Company</th>
              <th className="py-2 pr-4 font-semibold">Reason</th>
              <th className="py-2 pr-4 font-semibold">Added</th>
              <th className="py-2 pr-4 font-semibold">Ends</th>
              <th className="py-2 pr-4 font-semibold">Status</th>
              <th className="py-2 font-semibold"><span className="sr-only">Remove</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.items.map((item) => (
              <tr key={item.organization_id}>
                <td className="py-3 pr-4 font-medium text-text">{item.company_name ?? 'Unnamed company'}</td>
                <td className="py-3 pr-4 text-text-muted max-w-xs break-words">{item.reason}</td>
                <td className="py-3 pr-4 text-text-muted whitespace-nowrap">{formatDate(item.created_at)}</td>
                <td className="py-3 pr-4 text-text-muted whitespace-nowrap">
                  {item.expires_at ? formatDate(item.expires_at) : 'Never'}
                </td>
                <td className="py-3 pr-4"><StatusBadge active={item.is_active} /></td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onRemove(item)}
                    disabled={removingId === item.organization_id}
                    aria-label={`Remove ${item.company_name ?? 'company'}`}
                    className="inline-flex items-center gap-1 text-xs text-red-700 hover:underline disabled:opacity-50"
                  >
                    <Trash2 size={13} /> Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-text-muted">
        <span>Showing {from} to {to} of {data.total}</span>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" disabled={offset === 0} onClick={() => onPage(offset - PAGE_SIZE)}>
            Previous
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={to >= data.total} onClick={() => onPage(offset + PAGE_SIZE)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

/**
 * Plan exemptions - /admin/plan-exemptions (ADMIN only)
 *
 * Companies on this list keep Professional access once plan gating is switched on.
 * Calls
 *   GET    /api/v1/admin/plan-exemptions?limit=&offset=
 *   POST   /api/v1/admin/plan-exemptions
 *   DELETE /api/v1/admin/plan-exemptions/{organization_id}
 */
export default function AdminPlanExemptionsPage() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [status, setStatus] = useState('loading') // loading | ready | error
  const [offset, setOffset] = useState(0)
  // Bumping this number makes the effect below fetch the page again.
  const [reloadKey, setReloadKey] = useState(0)
  const [removingId, setRemovingId] = useState(null)
  const [actionError, setActionError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get(URL, { params: { limit: PAGE_SIZE, offset } })
      .then(({ data: page }) => {
        if (cancelled) return
        // Removing the last row of a later page leaves it empty: step back one page.
        if (page.items.length === 0 && offset > 0) {
          setOffset(Math.max(0, offset - PAGE_SIZE))
          return
        }
        setData(page)
        setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [offset, reloadKey])

  const reload = () => setReloadKey((n) => n + 1)

  // A new entry is listed first, so go back to the first page to show it.
  const handleAdded = () => {
    if (offset === 0) reload()
    else setOffset(0)
  }

  const handleRemove = async (item) => {
    const name = item.company_name ?? 'this company'
    if (!window.confirm(`Take ${name} off the list? It goes back to its normal plan straight away.`)) return
    setActionError(null)
    setRemovingId(item.organization_id)
    try {
      await api.delete(`${URL}/${item.organization_id}`)
      reload()
    } catch (err) {
      setActionError(errorText(err, 'Could not remove it. Please try again.'))
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <AdminLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text">Plan exemptions</h1>
          <p className="text-text-muted text-sm mt-1">
            Companies on this list keep Professional access even after plan gating is switched on,
            for example pilot customers, partners and test accounts. A company that pays for a plan
            keeps that plan. Until gating is switched on, every company already has Professional
            access.
          </p>
        </div>

        <AddSection onAdded={handleAdded} />

        <section className="bg-white rounded-xl border border-border p-6 shadow-sm space-y-4">
          <h2 className="text-lg font-semibold text-text">Companies on the list</h2>
          <ExemptionList
            data={data}
            status={status}
            offset={offset}
            onPage={setOffset}
            onRetry={reload}
            onRemove={handleRemove}
            removingId={removingId}
            actionError={actionError}
          />
        </section>
      </div>
    </AdminLayout>
  )
}
