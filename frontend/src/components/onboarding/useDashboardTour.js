import { useMemo } from 'react'
import { useGuidedTour } from './useGuidedTour'
import { EMPLOYER_STEPS } from './tourSteps'

/**
 * Part 1 of the employer tour, on the dashboard. Its last step leads to the example job
 * page (`onSeeExample`), where part 2 continues and ends the tour, so closing part 1 is
 * always "skipped" and moving on records nothing yet.
 */
export function useDashboardTour({ autoStart, onSeeExample }) {
  const steps = useMemo(
    () => EMPLOYER_STEPS.map((step) => (
      step.handoff
        ? { ...step, onNext: ({ leave }) => { leave(); onSeeExample() } }
        : step
    )),
    [onSeeExample],
  )
  return useGuidedTour({ steps, autoStart, completesTour: false })
}
