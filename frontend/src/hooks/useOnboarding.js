import { useContext, useEffect } from 'react'
import { OnboardingContext } from '@/context/onboardingState'

export function useOnboarding() {
  return useContext(OnboardingContext)
}

/** Report a checklist step as done when the page that shows it is opened. */
export function useReportStep(step) {
  const { markStep } = useOnboarding()
  useEffect(() => {
    markStep(step)
  }, [step, markStep])
}
