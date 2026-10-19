import { useCallback, useEffect, useRef } from 'react'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import './tour.css'
import { useOnboarding } from '@/hooks/useOnboarding'
import { tourSelector } from './tourSteps'

// Give the page a moment to lay out before pointing at it.
const AUTO_START_DELAY_MS = 800
// A step inside a tab or a dialog waits this long for its element to appear.
const WAIT_FOR_ELEMENT_MS = 2000

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Runs a guided tour of one page. Each step is
 * `{ target, title, description, side, align, nextLabel?, enter?, onNext? }`:
 *  - `target` is the value of the `data-tour` attribute to point at;
 *  - `enter()` is called just before the step is shown, to put the page in the right
 *    state (open a tab, open a dialog);
 *  - `onNext({ leave })` replaces the Next button, for a step that moves on to another
 *    page: `leave()` closes the tour without recording anything.
 *
 * It starts by itself once when `autoStart` is true and the server says this person has
 * not seen the tour (or always, with `startWhen: 'always'`, for a page only the tour
 * leads to). `start` runs it again on request.
 *
 * Only a first run is recorded on the server. With `completesTour` true, finishing the
 * last step is COMPLETED and leaving earlier is SKIPPED; with it false (a tour that goes
 * on to another page) leaving is always SKIPPED. Leaving the page halfway records
 * nothing, so the tour comes back next time. `onClosed(outcome)` runs after the person
 * closes or finishes it.
 */
export function useGuidedTour({
  steps,
  autoStart,
  startWhen = 'pending',
  completesTour = true,
  skipMissing = true,
  progressText = '{{current}} of {{total}}',
  onClosed,
}) {
  const { loaded, tourStatus, finishTour } = useOnboarding()
  const statusRef = useRef(tourStatus)
  const finishRef = useRef(finishTour)
  const closedRef = useRef(onClosed)
  const driverRef = useRef(null)
  const autoStartedRef = useRef(false)

  useEffect(() => {
    statusRef.current = tourStatus
    finishRef.current = finishTour
    closedRef.current = onClosed
  }, [tourStatus, finishTour, onClosed])

  const start = useCallback(() => {
    const list = skipMissing
      ? steps.filter((step) => document.querySelector(tourSelector(step.target)))
      : steps
    if (list.length === 0) return false

    driverRef.current?.destroy()
    const reduceMotion = prefersReducedMotion()

    const close = (reachedEnd) => {
      tour.destroy()
      driverRef.current = null
      const outcome = completesTour && reachedEnd ? 'COMPLETED' : 'SKIPPED'
      if (statusRef.current === 'PENDING') finishRef.current(outcome)
      closedRef.current?.(outcome)
    }
    const leave = () => {
      tour.destroy()
      driverRef.current = null
    }

    const tour = driver({
      steps: list.map((step, index) => ({
        element: tourSelector(step.target),
        popover: {
          title: step.title,
          description: step.description,
          side: step.side,
          align: step.align,
          // Only when a step has its own label: an undefined value would hide the
          // automatic "Done" on the last step.
          ...(step.nextLabel ? { nextBtnText: step.nextLabel } : {}),
          onNextClick: () => {
            if (step.onNext) {
              step.onNext({ leave })
              return
            }
            list[index + 1]?.enter?.()
            tour.moveNext()
          },
          onPrevClick: () => {
            list[index - 1]?.enter?.()
            tour.movePrevious()
          },
        },
      })),
      showProgress: true,
      progressText,
      nextBtnText: 'Next',
      prevBtnText: 'Back',
      doneBtnText: 'Done',
      popoverClass: 'elevare-tour',
      animate: !reduceMotion,
      smoothScroll: !reduceMotion,
      waitForElement: WAIT_FOR_ELEMENT_MS,
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
    list[0]?.enter?.()
    tour.drive()
    return true
  }, [steps, completesTour, skipMissing, progressText])

  useEffect(() => {
    const allowed = startWhen === 'always' || (loaded && tourStatus === 'PENDING')
    if (!autoStart || !allowed || autoStartedRef.current) return undefined
    const timer = window.setTimeout(() => {
      autoStartedRef.current = true
      start()
    }, AUTO_START_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [autoStart, startWhen, loaded, tourStatus, start])

  // Leaving the page mid-tour: remove the overlay, record nothing.
  useEffect(() => () => {
    driverRef.current?.destroy()
    driverRef.current = null
  }, [])

  return { start }
}
