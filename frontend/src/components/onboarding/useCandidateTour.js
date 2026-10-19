import { useGuidedTour } from './useGuidedTour'
import { CANDIDATE_STEPS } from './tourSteps'

/** The tour of the candidate dashboard: what makes a profile complete, and where the CV goes. */
export function useCandidateTour({ autoStart }) {
  return useGuidedTour({ steps: CANDIDATE_STEPS, autoStart })
}
