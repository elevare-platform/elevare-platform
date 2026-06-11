const VARIANTS = {
  // Account status
  ACTIVE: 'bg-green-100 text-green-700',
  PENDING_VERIFICATION: 'bg-yellow-100 text-yellow-700',
  SUSPENDED: 'bg-orange-100 text-orange-700',
  DEACTIVATED: 'bg-gray-100 text-gray-600',
  BANNED: 'bg-red-100 text-red-700',
  // Job status
  DRAFT: 'bg-gray-100 text-gray-600',
  CLOSED: 'bg-red-100 text-red-700',
  // Moderation
  PENDING: 'bg-yellow-100 text-yellow-700',
  APPROVED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-red-100 text-red-700',
  // Application
  SUBMITTED: 'bg-blue-100 text-blue-700',
  REVIEWING: 'bg-purple-100 text-purple-700',
  SHORTLISTED: 'bg-indigo-100 text-indigo-700',
  HIRED: 'bg-green-100 text-green-700',
  // Roles
  ADMIN: 'bg-purple-100 text-purple-700',
  EMPLOYER: 'bg-blue-100 text-blue-700',
  CANDIDATE: 'bg-gray-100 text-gray-600',
}

export default function StatusBadge({ value }) {
  const cls = VARIANTS[value] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {value?.replace(/_/g, ' ')}
    </span>
  )
}
