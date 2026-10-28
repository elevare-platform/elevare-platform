// What the shared interview results page shows about a candidate's interview.

export const STATUS = {
  COMPLETED: { label: 'Completed', className: 'bg-green-50 text-green-700 border-green-200' },
  ENDED: { label: 'Ended early', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  IN_PROGRESS: { label: 'Interview in progress', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  INVITED: { label: 'Invited', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  NOT_COMPLETED: { label: 'Not completed', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  NOT_INVITED: { label: 'Not interviewed yet', className: 'bg-gray-100 text-gray-600 border-gray-200' },
}

export function scoreColour(score) {
  if (score == null) return 'bg-gray-100 text-gray-500'
  if (score <= 40) return 'bg-red-100 text-red-600'
  if (score <= 70) return 'bg-amber-100 text-amber-700'
  return 'bg-green-100 text-green-700'
}

/** Whether there is anything to open for this candidate: an interview, or a CV assessment. */
export function hasDetail(candidate) {
  return Boolean(
    candidate.status === 'COMPLETED' ||
      candidate.status === 'ENDED' ||
      candidate.cv_score != null ||
      candidate.cv_summary ||
      candidate.cv_strengths?.length,
  )
}
