import { useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import api from '@/lib/api'

// How many interviews moved from one band to another, said once per move: "Hold for evidence to
// Shortlist: 3". A score that became incomplete has no band to move to.
function moves(changes) {
  const counts = new Map()
  for (const change of changes) {
    const key = `${change.from_band ?? 'No band'} to ${change.to_band ?? 'No band'}`
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].filter(([key]) => {
    const [from, to] = key.split(' to ')
    return from !== to
  })
}

/**
 * RecalculateBands - the admin's button that weighs every scored interview of a job again under the
 * job's CURRENT scoring profile (its weights, key marks, minimum key rating and band cut-offs), from
 * the ratings already saved. No model is called and no rating changes, so it is quick and safe to
 * repeat. It asks first, then says what it did. `onDone` runs after it has changed something so the
 * list can be read again. Elevare admins only (the server refuses anyone else).
 */
export default function RecalculateBands({ jobId, onDone }) {
  const [step, setStep] = useState('idle') // idle | confirming | working | done
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const run = async () => {
    if (step === 'working') return
    setStep('working')
    setError(null)
    try {
      const { data } = await api.post(`/api/v1/interviews/jobs/${jobId}/recalculate-bands`)
      setResult(data)
      setStep('done')
      if (data.changed > 0) onDone?.()
    } catch (err) {
      const message = err?.response?.data?.message
      setError(
        err?.response
          ? (typeof message === 'string' ? message : 'Something went wrong. Please try again.')
          : 'We could not reach the server. Check your connection and try again.'
      )
      setStep('confirming')
    }
  }

  return (
    <div className="space-y-2 rounded-xl border border-border bg-white px-4 py-3" data-testid="recalculate-bands">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-text">Recalculate the bands with the current scoring profile</p>
          <p className="text-xs text-text-muted">
            After you change this job&apos;s scoring profile (cut-offs, weights, key competencies), results already scored
            keep the old ones. This applies the new ones to the ratings already saved.
          </p>
        </div>
        {(step === 'idle' || step === 'done') && (
          <button
            type="button"
            onClick={() => {
              setResult(null)
              setStep('confirming')
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-brand-blue px-3 py-1.5 text-xs font-semibold text-brand-blue hover:bg-brand-blue/5"
          >
            <RefreshCw size={13} aria-hidden="true" /> Recalculate bands
          </button>
        )}
      </div>

      {(step === 'confirming' || step === 'working') && (
        <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p>
            Every scored interview of this job is weighed again under the profile as it is now. No ratings change and
            nothing is sent to the model. The totals, the bands, the key competency flags and the score and band lines in
            each written assessment follow the profile. An admin&apos;s own typed totals and edited text stay. It is safe to
            run twice.
          </p>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={run}
              disabled={step === 'working'}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-3 py-1.5 font-semibold text-white disabled:opacity-50"
            >
              {step === 'working' && <Loader2 size={12} className="animate-spin" aria-hidden="true" />}
              Yes, recalculate
            </button>
            <button
              type="button"
              onClick={() => setStep('idle')}
              disabled={step === 'working'}
              className="font-medium text-brand-blue hover:underline disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}

      {step === 'done' && result && (
        <div role="status" className="space-y-1 text-xs text-text" data-testid="recalculate-result">
          <p className="font-semibold">
            {result.checked === 0
              ? 'There are no scored interviews on this job.'
              : result.changed === 0
                ? `Checked ${result.checked} interview${result.checked === 1 ? '' : 's'}: nothing needed to change.`
                : `Checked ${result.checked} interview${result.checked === 1 ? '' : 's'}: ${result.changed} changed, ${result.unchanged} unchanged.`}
          </p>
          {moves(result.changes).length > 0 && (
            <ul className="list-disc pl-5 text-text-muted">
              {moves(result.changes).map(([move, count]) => (
                <li key={move}>
                  {move}: {count}
                </li>
              ))}
            </ul>
          )}
          {result.incomplete > 0 && (
            <p className="text-amber-800">
              {result.incomplete} now {result.incomplete === 1 ? 'has' : 'have'} no total or band, because the profile has a
              competency that interview never covered. Score {result.incomplete === 1 ? 'it' : 'them'} again to fill it in.
            </p>
          )}
          {result.skipped > 0 && (
            <p className="text-text-muted">
              {result.skipped} skipped (being scored again right now, or no ratings saved).
            </p>
          )}
        </div>
      )}
    </div>
  )
}
