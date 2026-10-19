import { useMemo } from 'react'
import { useGuidedTour } from './useGuidedTour'
import { EXAMPLE_JOB_STEPS } from './tourSteps'

/**
 * Part 2 of the employer tour, on the example job page. `setView` puts the page in the
 * state a step needs (which tab, whether a dialog or the score reasons are open);
 * `costText` is the real cost sentence when the account is charged for interviews.
 * Finishing the last step completes the tour; `onClosed` takes the person back to the
 * dashboard however it ends.
 */
export function useExampleJobTour({ setView, costText, onClosed, autoStart }) {
  const steps = useMemo(
    () => EXAMPLE_JOB_STEPS.map(({ view, ...step }) => ({
      ...step,
      description: step.target === 'example-cost' && costText ? costText : step.description,
      enter: () => setView(view),
    })),
    [setView, costText],
  )
  return useGuidedTour({
    steps,
    autoStart,
    startWhen: 'always',
    skipMissing: false,
    progressText: 'Example: {{current}} of {{total}}',
    onClosed,
  })
}
