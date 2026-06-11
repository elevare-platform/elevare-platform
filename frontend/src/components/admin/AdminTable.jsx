export function AdminTable({ children, empty, isEmpty }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-white">
      {isEmpty ? (
        <div className="flex flex-col items-center justify-center py-16 text-center px-4">
          <p className="text-text-muted text-sm">{empty ?? 'No records found.'}</p>
        </div>
      ) : (
        <table className="w-full text-sm">{children}</table>
      )}
    </div>
  )
}

export function Th({ children }) {
  return (
    <th className="px-4 py-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider bg-surface-muted border-b border-border">
      {children}
    </th>
  )
}

export function Td({ children, className = '' }) {
  return (
    <td className={`px-4 py-3 border-b border-border last:border-0 ${className}`}>
      {children}
    </td>
  )
}

export function Pagination({ cursor, onLoadMore, loading }) {
  if (!cursor) return null
  return (
    <div className="flex justify-center py-4 border-t border-border">
      <button
        onClick={onLoadMore}
        disabled={loading}
        className="text-sm text-brand-blue hover:underline disabled:opacity-50"
      >
        {loading ? 'Loading…' : 'Load more'}
      </button>
    </div>
  )
}
