import { useEffect, useState } from 'react'
import { DollarSign, FileSearch, Video, Mic, Brain, Target, RefreshCw } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import CostCard from '@/components/admin/CostCard'
import CostTrendChart from '@/components/admin/CostTrendChart'
import CostTrendRangeSelector from '@/components/admin/CostTrendRangeSelector'
import { presetRange } from '@/lib/costTrendRange'
import { useAdmin } from '@/hooks/useAdmin'

const COMPONENT_META = {
  realtime: { label: 'Realtime (live voice)', icon: Video },
  transcription: { label: 'Transcription (Whisper fallback)', icon: Mic },
  scoring: { label: 'Scoring (Claude)', icon: Brain },
}

const TOTAL_LINES = [
  { key: 'cv', label: 'CV parsing', color: '#2563eb' },
  { key: 'interview', label: 'AI interviews', color: '#16a34a' },
  { key: 'fitScoring', label: 'Fit scoring', color: '#d97706' },
]

const COMPONENT_LINES = [
  { key: 'realtime', label: 'Realtime', color: '#2563eb' },
  { key: 'transcription', label: 'Transcription', color: '#16a34a' },
  { key: 'scoring', label: 'Scoring', color: '#d97706' },
]

/** Merge several {month, total_cost_usd}[] series into one Recharts-ready
 * dataset keyed by month, one field per series. A month missing from a
 * given series' response (before that category had any data) is left
 * undefined, which reads as a gap rather than a misleading 0. */
function mergeTrendSeries(seriesMap) {
  const monthSet = new Set()
  Object.values(seriesMap).forEach((arr) => arr?.forEach((p) => monthSet.add(p.month)))
  const months = Array.from(monthSet).sort()
  return months.map((month) => {
    const point = { month }
    for (const [key, arr] of Object.entries(seriesMap)) {
      const found = arr?.find((p) => p.month === month)
      point[key] = found ? found.total_cost_usd : undefined
    }
    return point
  })
}

function interviewComponentSeries(interviewTrend) {
  return (interviewTrend ?? []).map((point) => ({
    month: point.month,
    realtime: point.by_component?.realtime?.total_cost_usd,
    transcription: point.by_component?.transcription?.total_cost_usd,
    scoring: point.by_component?.scoring?.total_cost_usd,
  }))
}

export default function AdminCostsPage() {
  const {
    getCvParsingCosts,
    getInterviewCosts,
    getFitScoringCosts,
    getCvParsingCostTrend,
    getInterviewCostTrend,
    getFitScoringCostTrend,
    loading,
  } = useAdmin()
  const [cvCosts, setCvCosts] = useState(null)
  const [interviewCosts, setInterviewCosts] = useState(null)
  const [fitScoringCosts, setFitScoringCosts] = useState(null)

  const [activePreset, setActivePreset] = useState(3)
  const [customFrom, setCustomFrom] = useState(undefined)
  const [customTo, setCustomTo] = useState(undefined)
  const [cvTrend, setCvTrend] = useState(null)
  const [interviewTrend, setInterviewTrend] = useState(null)
  const [fitScoringTrend, setFitScoringTrend] = useState(null)

  const fetchAll = () => {
    getCvParsingCosts().then(setCvCosts).catch(() => {})
    getInterviewCosts().then(setInterviewCosts).catch(() => {})
    getFitScoringCosts().then(setFitScoringCosts).catch(() => {})
  }

  useEffect(() => { fetchAll() }, [])

  const { from, to } = customFrom || customTo
    ? { from: customFrom, to: customTo }
    : presetRange(activePreset)

  useEffect(() => {
    getCvParsingCostTrend(from, to).then((r) => setCvTrend(r.series)).catch(() => {})
    getInterviewCostTrend(from, to).then((r) => setInterviewTrend(r.series)).catch(() => {})
    getFitScoringCostTrend(from, to).then((r) => setFitScoringTrend(r.series)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, to])

  const combinedTrendData = mergeTrendSeries({
    cv: cvTrend,
    interview: interviewTrend?.map((p) => ({ month: p.month, total_cost_usd: p.total_cost_usd })),
    fitScoring: fitScoringTrend,
  })
  const componentTrendData = interviewComponentSeries(interviewTrend)

  const byComponent = interviewCosts?.by_component ?? {}
  const componentKeys = ['realtime', 'transcription', 'scoring']

  // Combined total is only a real number if no side has unpriced calls
  // this month — otherwise it's a lower bound wearing a $ sign, which is
  // worse than admitting the total is unknown.
  const cvUnpriced = cvCosts && cvCosts.total_cost_usd == null && cvCosts.total_llm_calls > 0
  const interviewUnpriced = interviewCosts && interviewCosts.total_cost_usd == null && interviewCosts.total_calls > 0
  const fitScoringUnpriced = fitScoringCosts && fitScoringCosts.total_cost_usd == null && fitScoringCosts.total_llm_calls > 0
  const combinedTotal = (!cvUnpriced && !interviewUnpriced && !fitScoringUnpriced && cvCosts && interviewCosts && fitScoringCosts)
    ? (cvCosts.total_cost_usd ?? 0) + (interviewCosts.total_cost_usd ?? 0) + (fitScoringCosts.total_cost_usd ?? 0)
    : null
  const combinedCalls = (cvCosts?.total_llm_calls ?? 0) + (interviewCosts?.total_calls ?? 0) + (fitScoringCosts?.total_llm_calls ?? 0)

  return (
    <AdminLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text">AI Cost Tracking</h1>
          <p className="text-sm text-text-muted mt-1">
            {cvCosts?.month ?? interviewCosts?.month ?? ''}
          </p>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-border hover:bg-surface-muted transition-colors disabled:opacity-50"
          aria-label="Refresh costs"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <CostCard
          label="Combined total"
          costUsd={combinedTotal}
          calls={combinedCalls}
          icon={DollarSign}
        />
        <CostCard
          label="CV parsing"
          costUsd={cvCosts?.total_cost_usd}
          calls={cvCosts?.total_llm_calls ?? 0}
          icon={FileSearch}
        />
        <CostCard
          label="AI interviews"
          costUsd={interviewCosts?.total_cost_usd}
          calls={interviewCosts?.total_calls ?? 0}
          icon={Video}
        />
        <CostCard
          label="Fit scoring (CV vs job)"
          costUsd={fitScoringCosts?.total_cost_usd}
          calls={fitScoringCosts?.total_llm_calls ?? 0}
          icon={Target}
        />
      </div>

      <h2 className="text-sm font-semibold text-text mb-4">
        Interview cost by component
      </h2>
      <p className="text-xs text-text-muted mb-4 -mt-2">
        The live voice conversation (realtime) is normally the dominant cost —
        this breakdown is what makes that visible instead of one opaque total.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {componentKeys.map((key) => {
          const meta = COMPONENT_META[key]
          const entry = byComponent[key]
          return (
            <CostCard
              key={key}
              label={meta.label}
              costUsd={entry?.total_cost_usd}
              calls={entry?.total_calls ?? 0}
              icon={meta.icon}
            />
          )
        })}
      </div>

      <h2 className="text-sm font-semibold text-text mb-1">Cost trends</h2>
      <p className="text-xs text-text-muted mb-4">
        Monthly totals over the selected range — a gap in a line means real
        calls happened that month for a model with no configured price, not
        zero spend.
      </p>
      <CostTrendRangeSelector
        activePreset={activePreset}
        onPresetChange={(months) => {
          setActivePreset(months)
          setCustomFrom(undefined)
          setCustomTo(undefined)
        }}
        customFrom={customFrom}
        customTo={customTo}
        onCustomChange={({ from: f, to: t }) => {
          setCustomFrom(f)
          setCustomTo(t)
        }}
      />

      <div className="bg-white rounded-xl border border-border p-5 mb-6">
        <h3 className="text-xs font-semibold text-text-muted mb-3 uppercase tracking-wide">
          Total cost by category
        </h3>
        <CostTrendChart data={combinedTrendData} lines={TOTAL_LINES} />
      </div>

      <div className="bg-white rounded-xl border border-border p-5 mb-8">
        <h3 className="text-xs font-semibold text-text-muted mb-3 uppercase tracking-wide">
          Interview cost by component
        </h3>
        <CostTrendChart data={componentTrendData} lines={COMPONENT_LINES} />
      </div>

      <div className="bg-white rounded-xl border border-border p-5 text-xs text-text-muted leading-relaxed">
        Every $/unit rate behind these numbers lives in{' '}
        <code className="font-mono bg-surface-muted px-1 py-0.5 rounded">
          backend/app/core/ai_pricing.py
        </code>{' '}
        and is a placeholder until checked against Anthropic's and OpenAI's live
        pricing pages. "Unknown" above means real, billed calls happened this
        month for a model not yet in that pricing table — add its rate there to
        turn it into a real number; the underlying token/duration counts are
        never lost in the meantime.
      </div>
    </AdminLayout>
  )
}
