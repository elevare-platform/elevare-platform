const CONFIG = {
  pending:    { label: 'Pending',    classes: 'bg-gray-100 text-gray-600' },
  processing: { label: 'Processing', classes: 'bg-blue-100 text-blue-700 animate-pulse' },
  completed:  { label: 'Completed',  classes: 'bg-green-100 text-green-700' },
  flagged:    { label: 'Flagged',    classes: 'bg-amber-100 text-amber-700' },
  failed:     { label: 'Failed',     classes: 'bg-red-100 text-red-700' },
}

export default function CVParseStatusBadge({ status }) {
  const cfg = CONFIG[status] ?? CONFIG.pending
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cfg.classes}`}>
      {cfg.label}
    </span>
  )
}
