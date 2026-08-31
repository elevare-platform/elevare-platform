import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'

function formatUsd(value) {
  if (value == null) return 'Unknown'
  return value.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-border rounded-lg shadow-md p-3 text-xs">
      <p className="font-semibold text-text mb-1">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} style={{ color: entry.color }}>
          {entry.name}: {formatUsd(entry.value)}
        </p>
      ))}
    </div>
  )
}

/**
 * A monthly line chart for one or more cost series. A gap in a line means
 * "unknown cost that month" (real calls happened but the model wasn't
 * priced) — see app/core/ai_pricing.py — not zero spend.
 *
 * `lines`: [{ key, label, color }] — key must match a field on each point
 * in `data` (points come pre-filled with 0 for genuinely quiet months and
 * null for unpriced months, from the backend's month-fill logic).
 */
export default function CostTrendChart({ data, lines, height = 280 }) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-text-muted bg-surface-muted rounded-lg"
        style={{ height }}
      >
        No data for this range yet.
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
        <YAxis
          tick={{ fontSize: 12 }}
          tickFormatter={(v) => `$${v}`}
          width={56}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {lines.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={line.color}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
