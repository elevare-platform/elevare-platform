import { createContext } from 'react'

// Pages that report a checklist step are also rendered on their own in tests and
// previews, so without a provider every call is a quiet no-op.
export const NOOP_ONBOARDING = {
  loaded: false,
  tourStatus: null,
  completedSteps: [],
  checklistDismissed: false,
  markStep: () => {},
  finishTour: () => {},
  dismissChecklist: () => {},
}

export const OnboardingContext = createContext(NOOP_ONBOARDING)
