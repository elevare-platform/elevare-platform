import { useCallback, useEffect, useRef } from 'react'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import './tour.css'
import { useOnboarding } from '@/hooks/useOnboarding'
import { TOUR_STEPS, tourSelector } from './tourSteps'

// Give the page a moment to lay out (and the tabs to render) before pointing at it.
const AUTO_START_DELAY_MS = 800

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Runs the dashboard tour.
 *
 * It starts by itself once, when the server says this person has not seen it
 * (`autoStart` says the page is ready, e.g. the overview tab is showing). `start` runs
 * it again on request (the Help button). Only the first run is recorded on the server:
 * finishing the last step is COMPLETED, leaving earlier is SKIPPED. Leaving the page
 * halfway records nothing, so the tour comes back next time.
 */
export function useDashboardTour({ autoStart }) {
  const { loaded, tourStatus, finishTour } = useOnboarding()
  const statusRef = useRef(tourStatus)
  const finishRef = useRef(finishTour)
  const driverRef = useRef(null)
  const autoStartedRef = useRef(false)

  useEffect(() => {
    statusRef.current = tourStatus
    finishRef.current = finishTour
  }, [tourStatus, finishTour])

  const start = useCallback(() => {
    const steps = TOUR_STEPS
      .filter((step) => document.querySelector(tourSelector(step.target)))
      .map((step) => ({
        element: tourSelector(step.target),
        popover: {
          title: step.title,
          description: step.description,
          side: step.side,
          align: step.align,
        },
      }))
    if (steps.length === 0) return false

    driverRef.current?.destroy()
    const reduceMotion = prefersReducedMotion()

    const close = (reachedEnd) => {
      tour.destroy()
      driverRef.current = null
      if (statusRef.current === 'PENDING') {
        finishRef.current(reachedEnd ? 'COMPLETED' : 'SKIPPED')
      }
    }

    const tour = driver({
      steps,
      showProgress: true,
      progressText: '{{current}} of {{total}}',
      nextBtnText: 'Next',
      prevBtnText: 'Back',
      doneBtnText: 'Done',
      popoverClass: 'elevare-tour',
      animate: !reduceMotion,
      smoothScroll: !reduceMotion,
      stagePadding: 6,
      stageRadius: 10,
      overlayOpacity: 0.55,
      // A stray click on the dimmed page must not end the tour for good.
      overlayClickBehavior: () => {},
      onDestroyStarted: () => close(tour.isLastStep()),
      onPopoverRender: (popover) => {
        const skip = document.createElement('button')
        skip.type = 'button'
        skip.className = 'elevare-tour-skip'
        skip.textContent = 'Skip tour'
        skip.addEventListener('click', () => close(false))
        popover.description.after(skip)
      },
    })
    driverRef.current = tour
    tour.drive()
    return true
  }, [])

  useEffect(() => {
    if (!autoStart || !loaded || tourStatus !== 'PENDING' || autoStartedRef.current) {
      return undefined
    }
    const timer = window.setTimeout(() => {
      autoStartedRef.current = true
      start()
    }, AUTO_START_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [autoStart, loaded, tourStatus, start])

  // Leaving the page mid-tour: remove the overlay, record nothing.
  useEffect(() => () => {
    driverRef.current?.destroy()
    driverRef.current = null
  }, [])

  return { start }
}
