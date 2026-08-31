export function presetRange(months) {
  if (months == null) return { from: undefined, to: undefined }
  const to = new Date()
  const from = new Date()
  from.setMonth(from.getMonth() - months)
  const toISODate = (d) => d.toISOString().slice(0, 10)
  return { from: toISODate(from), to: toISODate(to) }
}
