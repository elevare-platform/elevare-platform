// Groups a user's jobs by status for a job picker, so a long list reads as
// "Active" and "Drafts" instead of one undifferentiated column.
//
// Closed jobs are left out: they are noise when choosing a job to work on, unless
// one is already chosen (for example it is named in the address), in which case it
// is shown so the selection is not blank. A job with no known status counts as
// active, which is how the picker behaved before drafts were offered.
export function groupJobsByStatus(jobs, selectedId) {
  const active = []
  const drafts = []
  const closed = []
  for (const job of jobs ?? []) {
    if (job.status === 'CLOSED') {
      if (job.id === selectedId) closed.push(job)
    } else if (job.status === 'DRAFT') {
      drafts.push(job)
    } else {
      active.push(job)
    }
  }
  return [
    { label: 'Active', jobs: active },
    { label: 'Drafts (not yet published)', jobs: drafts },
    { label: 'Closed', jobs: closed },
  ].filter((group) => group.jobs.length > 0)
}
