/**
 * ReviewedTag - the small grey "Reviewed" tag beside a score that a person at Elevare has set in
 * place of the one the system worked out. It says nothing about who or why.
 */
export default function ReviewedTag() {
  return (
    <span
      data-testid="reviewed-tag"
      className="inline-block rounded-full border border-border bg-surface-muted px-2 py-0.5 text-[10px] font-medium text-text-muted"
    >
      Reviewed
    </span>
  )
}
