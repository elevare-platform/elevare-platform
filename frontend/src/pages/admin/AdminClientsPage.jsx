import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Copy, Check, UserPlus, Briefcase, X, Search } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// ─── Schemas ──────────────────────────────────────────────────────────────────
// The server applies the same limits (names are 30 characters because that is the
// size of the database columns) and stays the authority.

const accountSchema = z.object({
  first_name: z.string().trim().min(1, 'First name is required').max(30, 'At most 30 characters'),
  last_name: z.string().trim().min(1, 'Last name is required').max(30, 'At most 30 characters'),
  email: z.string().email('Enter a valid email address'),
  phone_number: z
    .string()
    .trim()
    .regex(/^(\+\d{8,15})?$/, 'Use international format, for example +2348031234567')
    .optional(),
  company_name: z.string().trim().min(1, 'Company name is required').max(255, 'At most 255 characters'),
})

const jobSchema = z.object({
  title: z.string().trim().min(3, 'At least 3 characters').max(150, 'At most 150 characters'),
  location: z.string().trim().min(1, 'Location is required').max(255, 'At most 255 characters'),
  contract_type: z.enum(['FULL_TIME', 'PART_TIME', 'FREELANCE', 'INTERNSHIP', 'CONTRACT']),
  work_location: z.enum(['LOCAL', 'INTERNATIONAL']),
  about_the_role: z.string().trim().min(10, 'At least 10 characters'),
  key_responsibilities: z.string().trim().min(10, 'At least 10 characters'),
  requirements: z.string().trim().min(10, 'At least 10 characters'),
})

const CONTRACT_TYPES = [
  ['FULL_TIME', 'Full time'],
  ['PART_TIME', 'Part time'],
  ['CONTRACT', 'Contract'],
  ['FREELANCE', 'Freelance'],
  ['INTERNSHIP', 'Internship'],
]

const selectClass =
  'flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue'
const textareaClass =
  'flex min-h-[88px] w-full rounded-md border border-border bg-surface px-3 py-2 text-sm placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue'

function serverMessage(err, fallback) {
  const body = err?.response?.data
  const message = body?.message ?? body?.detail
  return typeof message === 'string' ? message : fallback
}

// ─── The temporary password, shown once ───────────────────────────────────────

function TemporaryPasswordCard({ account, onDismiss }) {
  const [copied, setCopied] = useState(false)
  const [copyFailed, setCopyFailed] = useState(false)

  const details = `Login: ${window.location.origin}/login\nEmail: ${account.email}\nTemporary password: ${account.temporary_password}`

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(details)
      setCopied(true)
      setCopyFailed(false)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      setCopyFailed(true)
    }
  }

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-5 space-y-4" role="status">
      <div>
        <p className="text-sm font-semibold text-amber-900">Account created for {account.company_name}</p>
        <p className="text-xs text-amber-800 mt-0.5">
          Share these login details with the client. They must choose their own password on first login.
        </p>
      </div>

      <dl className="space-y-2 text-sm">
        <div>
          <dt className="text-xs font-medium text-amber-900">Email</dt>
          <dd><code className="block bg-white border border-amber-200 rounded-lg px-3 py-2 font-mono break-all">{account.email}</code></dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-amber-900">Temporary password</dt>
          <dd><code className="block bg-white border border-amber-200 rounded-lg px-3 py-2 font-mono tracking-wide">{account.temporary_password}</code></dd>
        </div>
      </dl>

      <p className="text-xs font-semibold text-red-700">
        This password is shown once and cannot be retrieved later. Copy it now.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            'flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors',
            copied ? 'bg-green-600 text-white' : 'bg-white border border-amber-300 text-amber-900 hover:bg-amber-100'
          )}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy login details'}
        </button>
        {copyFailed && (
          <span className="text-xs text-red-700">Copy failed. Select the password above and copy it by hand.</span>
        )}
        <button
          type="button"
          onClick={onDismiss}
          className="ml-auto text-xs font-medium text-amber-900 underline underline-offset-2"
        >
          I have saved it, hide
        </button>
      </div>
    </div>
  )
}

// ─── Create account ───────────────────────────────────────────────────────────

function CreateAccountSection({ onCreated }) {
  const [serverError, setServerError] = useState(null)
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(accountSchema),
  })

  const onSubmit = async (values) => {
    setServerError(null)
    try {
      const { data } = await api.post('/api/v1/admin/employers/provision', {
        ...values,
        phone_number: values.phone_number || null,
      })
      onCreated({ ...data, company_name: values.company_name })
      reset()
    } catch (err) {
      const status = err.response?.status
      if (status === 409) {
        setServerError(serverMessage(err, 'A user with this email or phone number already exists.'))
      } else if (status === 422) {
        setServerError('Please check the details and try again.')
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  return (
    <section className="bg-white rounded-xl border border-border p-6 shadow-sm space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-text">Create a client account</h2>
        <p className="text-sm text-text-muted mt-1">
          Creates an employer account with a temporary password. The client documents are not
          needed until they want to post a public job.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="grid sm:grid-cols-2 gap-4">
          <FormField>
            <Label htmlFor="first_name">First name</Label>
            <Input id="first_name" {...register('first_name')} />
            <FormMessage>{errors.first_name?.message}</FormMessage>
          </FormField>
          <FormField>
            <Label htmlFor="last_name">Last name</Label>
            <Input id="last_name" {...register('last_name')} />
            <FormMessage>{errors.last_name?.message}</FormMessage>
          </FormField>
        </div>
        <FormField>
          <Label htmlFor="client_email">Email address</Label>
          <Input id="client_email" type="email" {...register('email')} />
          <FormMessage>{errors.email?.message}</FormMessage>
        </FormField>
        <div className="grid sm:grid-cols-2 gap-4">
          <FormField>
            <Label htmlFor="phone_number">Phone number (optional)</Label>
            <Input id="phone_number" placeholder="+2348031234567" {...register('phone_number')} />
            <FormMessage>{errors.phone_number?.message}</FormMessage>
          </FormField>
          <FormField>
            <Label htmlFor="company_name">Company name</Label>
            <Input id="company_name" {...register('company_name')} />
            <FormMessage>{errors.company_name?.message}</FormMessage>
          </FormField>
        </div>

        {serverError && (
          <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {serverError}
          </div>
        )}

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? <><Loader2 size={15} className="mr-2 animate-spin" /> Creating…</>
            : <><UserPlus size={15} className="mr-2" /> Create account</>}
        </Button>
      </form>
    </section>
  )
}

// ─── Pick a client ────────────────────────────────────────────────────────────

function ClientPicker({ selected, onSelect }) {
  const [term, setTerm] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)

  // Debounced search of existing employer accounts.
  useEffect(() => {
    const trimmed = term.trim()
    if (trimmed.length < 2) return undefined
    let cancelled = false
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const { data } = await api.get('/api/v1/admin/users', {
          params: { role: 'EMPLOYER', search: trimmed, limit: 8 },
        })
        if (!cancelled) setResults(data.items ?? [])
      } catch {
        if (!cancelled) setResults([])
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [term])

  if (selected) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-muted px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-text truncate">{selected.label}</p>
          <p className="text-xs text-text-muted truncate">{selected.email}</p>
        </div>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text"
        >
          <X size={13} /> Change
        </button>
      </div>
    )
  }

  const visible = term.trim().length < 2 ? [] : results

  return (
    <div className="space-y-2">
      <Label htmlFor="client_search">Client</Label>
      <div className="relative">
        <Search size={14} className="absolute left-3 top-3 text-text-muted" aria-hidden="true" />
        <Input
          id="client_search"
          className="pl-9"
          placeholder="Search employers by name or email"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
        />
      </div>
      {searching && <p className="text-xs text-text-muted">Searching…</p>}
      {visible.length > 0 && (
        <ul className="rounded-lg border border-border divide-y divide-border bg-white">
          {visible.map((u) => (
            <li key={u.id}>
              <button
                type="button"
                onClick={() =>
                  onSelect({ id: u.id, label: `${u.first_name} ${u.last_name}`, email: u.email })
                }
                className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-muted"
              >
                {u.first_name} {u.last_name}
                <span className="block text-xs text-text-muted">{u.email}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ─── Interview-only draft jobs ────────────────────────────────────────────────

function InterviewJobsSection({ client, onClientChange }) {
  const [serverError, setServerError] = useState(null)
  const [created, setCreated] = useState([])
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(jobSchema),
    defaultValues: { contract_type: 'FULL_TIME', work_location: 'LOCAL' },
  })

  const onSubmit = async (values) => {
    if (!client) return
    setServerError(null)
    try {
      const { data } = await api.post(`/api/v1/admin/employers/${client.id}/jobs`, values)
      setCreated((prev) => [{ id: data.id, title: data.title, clientId: client.id }, ...prev])
      // Keep the shared fields, so the next role is quick to enter.
      reset({
        title: '',
        about_the_role: '',
        key_responsibilities: '',
        requirements: '',
        location: values.location,
        contract_type: values.contract_type,
        work_location: values.work_location,
      })
    } catch (err) {
      const status = err.response?.status
      if (status === 409) {
        setServerError(serverMessage(err, 'This account already has a job with that title.'))
      } else if (status === 404) {
        setServerError('That client account no longer exists.')
      } else if (status === 422) {
        setServerError(serverMessage(err, 'Please check the details and try again.'))
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  const clientJobs = created.filter((j) => j.clientId === client?.id)

  return (
    <section className="bg-white rounded-xl border border-border p-6 shadow-sm space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-text">Create interview jobs for a client</h2>
        <p className="text-sm text-text-muted mt-1">
          Adds a draft job to the client&apos;s account. A draft never appears on the public job
          board. <strong>The client writes the AI interview brief themselves</strong> on the Edit Job
          page, then adds candidates and sends the interviews. They will find the job under the
          Pending tab of My Jobs.
        </p>
      </div>

      <ClientPicker selected={client} onSelect={onClientChange} />

      {client && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField>
            <Label htmlFor="job_title">Job title</Label>
            <Input id="job_title" {...register('title')} />
            <FormMessage>{errors.title?.message}</FormMessage>
          </FormField>

          <div className="grid sm:grid-cols-3 gap-4">
            <FormField>
              <Label htmlFor="job_location">Location</Label>
              <Input id="job_location" placeholder="Lagos, Nigeria" {...register('location')} />
              <FormMessage>{errors.location?.message}</FormMessage>
            </FormField>
            <FormField>
              <Label htmlFor="contract_type">Contract</Label>
              <select id="contract_type" className={selectClass} {...register('contract_type')}>
                {CONTRACT_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </FormField>
            <FormField>
              <Label htmlFor="work_location">Work location</Label>
              <select id="work_location" className={selectClass} {...register('work_location')}>
                <option value="LOCAL">Local</option>
                <option value="INTERNATIONAL">International</option>
              </select>
            </FormField>
          </div>

          <FormField>
            <Label htmlFor="about_the_role">About the role</Label>
            <textarea id="about_the_role" className={textareaClass} {...register('about_the_role')} />
            <FormMessage>{errors.about_the_role?.message}</FormMessage>
          </FormField>
          <FormField>
            <Label htmlFor="key_responsibilities">Key responsibilities</Label>
            <textarea id="key_responsibilities" className={textareaClass} {...register('key_responsibilities')} />
            <FormMessage>{errors.key_responsibilities?.message}</FormMessage>
          </FormField>
          <FormField>
            <Label htmlFor="requirements">Requirements</Label>
            <textarea id="requirements" className={textareaClass} {...register('requirements')} />
            <FormMessage>{errors.requirements?.message}</FormMessage>
          </FormField>

          {serverError && (
            <div role="alert" className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {serverError}
            </div>
          )}

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting
              ? <><Loader2 size={15} className="mr-2 animate-spin" /> Creating…</>
              : <><Briefcase size={15} className="mr-2" /> Create draft job</>}
          </Button>
        </form>
      )}

      {clientJobs.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider">
            Created this session
          </h3>
          <ul className="space-y-1.5">
            {clientJobs.map((job) => (
              <li key={job.id} className="flex items-center gap-2 text-sm text-text">
                <Check size={14} className="text-green-600" aria-hidden="true" />
                {job.title}
                <span className="text-xs text-text-muted">Draft, no interview brief yet</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

/**
 * Client accounts - /admin/clients (ADMIN only)
 *
 * Create an employer account with a temporary password, and add interview-only
 * draft jobs to a client's account. Calls
 *   POST /api/v1/admin/employers/provision
 *   POST /api/v1/admin/employers/{id}/jobs
 */
export default function AdminClientsPage() {
  const [account, setAccount] = useState(null)
  const [client, setClient] = useState(null)

  const handleCreated = (created) => {
    setAccount(created)
    // Straight on to adding this client's jobs.
    setClient({ id: created.user_id, label: created.company_name, email: created.email })
  }

  return (
    <AdminLayout>
      <div className="max-w-3xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text">Client accounts</h1>
          <p className="text-text-muted text-sm mt-1">
            Set up a client so they can interview the candidates sourced for them.
          </p>
        </div>

        <CreateAccountSection onCreated={handleCreated} />

        {account && (
          <TemporaryPasswordCard account={account} onDismiss={() => setAccount(null)} />
        )}

        <InterviewJobsSection client={client} onClientChange={setClient} />
      </div>
    </AdminLayout>
  )
}
