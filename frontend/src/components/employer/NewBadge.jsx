// A CV or applicant that arrived since the employer first used the markers and that they have not
// opened yet (docs/08_DECISIONS.md, item 35).
export default function NewBadge() {
  return (
    <span
      data-testid="new-badge"
      className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-brand-blue text-white flex-shrink-0"
    >
      New
    </span>
  )
}
