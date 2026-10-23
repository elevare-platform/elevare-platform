import { numberedRuleGroups } from '@/lib/interviewRules'

/**
 * The rules a candidate reads and accepts before an AI interview. Numbered in one running
 * sequence across the groups, so a rule can be referred to by its number ("rule 8"). `groups`
 * chooses the rule set (the live interview's by default, or the strict interview's).
 */
export default function InterviewRules({ monitoring, groups }) {
  return (
    <div className="space-y-5" data-testid="interview-rules">
      {numberedRuleGroups(monitoring, groups).map((group) => (
        <section key={group.title} aria-label={group.title}>
          <h2 className="text-sm font-semibold text-text mb-2">{group.title}</h2>
          <ul className="space-y-2">
            {group.rules.map((rule) => (
              <li
                key={rule.id}
                className={
                  'flex items-start gap-2.5 text-sm leading-relaxed ' +
                  (rule.emphasis
                    ? 'rounded-lg border border-amber-300 bg-amber-50 p-2.5 font-medium text-amber-900'
                    : 'text-text-muted')
                }
              >
                <span
                  className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-brand-blue/10 text-[11px] font-semibold text-brand-blue mt-0.5"
                  aria-hidden="true"
                >
                  {rule.number}
                </span>
                <span>
                  <span className="sr-only">Rule {rule.number}. </span>
                  {rule.text}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
