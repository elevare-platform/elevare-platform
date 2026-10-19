// What one press of Rescore did, in a sentence or two, from the answer of
// POST /api/v1/rescore/jobs/{job_id}.
//   scoring: readable CVs scored again; reparsing: unreadable CVs being read again
//   in_progress: still being read, nothing to do yet; no_stored_file: unreadable and
//   there is no file to read again; remaining: still to do after this batch.
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

export function describeRescore(result) {
  if (!result) return ''
  const started = result.scoring + result.reparsing
  const parts = []

  if (started > 0) {
    let text = `Started ${plural(started, 'candidate', 'candidates')}`
    if (result.reparsing > 0) {
      text += `, ${plural(result.reparsing, 'CV is', 'CVs are')} being read again`
    }
    parts.push(text)
  }
  if (result.in_progress > 0) {
    parts.push(`${plural(result.in_progress, 'CV is', 'CVs are')} still being read, so there is nothing to do for them yet`)
  }
  if (result.no_stored_file > 0) {
    parts.push(
      `${plural(result.no_stored_file, 'CV', 'CVs')} could not be read and there is no stored file to read again, so ${result.no_stored_file === 1 ? 'it needs' : 'they need'} a new upload`
    )
  }
  if (result.remaining > 0) {
    parts.push(`${result.remaining} still to do: press Rescore again to go on`)
  }
  if (parts.length === 0) return 'Nothing needed rescoring.'
  return `${parts.join('. ')}.`
}
