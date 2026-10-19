import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import api from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { NOOP_ONBOARDING, OnboardingContext } from '@/context/onboardingState'

const BASE = '/api/v1/onboarding/me'

const fromServer = (userId, data) => ({
  userId,
  loaded: true,
  tourStatus: data.tour_status,
  completedSteps: data.completed_steps,
  checklistDismissed: data.checklist_dismissed,
})

/**
 * Where an employer is in the first-login tour and "Get started" checklist. Kept on the
 * server so it follows the person to another browser or device.
 *
 * `loaded` is false until the server has answered, and stays false if it cannot be
 * reached: the tour only starts when we know the person has not seen it, never on a guess.
 * The writes are best effort. Failing to save a step must never get in the way of the page.
 */
export function OnboardingProvider({ children }) {
  const { user } = useAuth()
  const userId = user?.id
  const isEmployer = user?.role === 'EMPLOYER'

  // Remembers whose progress this is, so after one person logs out and another logs in
  // the first person's progress is never shown while the second's is loading.
  const [state, setState] = useState({ ...NOOP_ONBOARDING, userId: null })
  // Steps already sent (or being sent) this session, so a page that re-renders or a
  // double click reports a step once.
  const reported = useRef(new Set())

  useEffect(() => {
    reported.current = new Set()
    if (!isEmployer) return undefined
    let cancelled = false
    api.get(BASE)
      .then(({ data }) => {
        if (cancelled) return
        // A step reported while this was loading may already be in the state; keep it.
        setState((s) => {
          const loaded = fromServer(userId, data)
          if (s.userId !== userId) return loaded
          return { ...loaded, completedSteps: [...new Set([...s.completedSteps, ...loaded.completedSteps])] }
        })
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [isEmployer, userId])

  const markStep = useCallback((step) => {
    if (!isEmployer || reported.current.has(step)) return
    reported.current.add(step)
    // Show it as done straight away; the server's answer replaces this.
    setState((s) => (
      s.userId !== userId || s.completedSteps.includes(step)
        ? s
        : { ...s, completedSteps: [...s.completedSteps, step] }
    ))
    api.post(`${BASE}/steps`, { step })
      .then(({ data }) => setState(fromServer(userId, data)))
      .catch(() => { reported.current.delete(step) })
  }, [isEmployer, userId])

  const finishTour = useCallback((outcome) => {
    if (!isEmployer) return
    setState((s) => (
      s.userId === userId && s.tourStatus === 'PENDING' ? { ...s, tourStatus: outcome } : s
    ))
    api.post(`${BASE}/tour`, { outcome })
      .then(({ data }) => setState(fromServer(userId, data)))
      .catch(() => {})
  }, [isEmployer, userId])

  const dismissChecklist = useCallback(() => {
    if (!isEmployer) return
    setState((s) => (s.userId === userId ? { ...s, checklistDismissed: true } : s))
    api.post(`${BASE}/checklist/dismiss`)
      .then(({ data }) => setState(fromServer(userId, data)))
      .catch(() => {})
  }, [isEmployer, userId])

  const value = useMemo(() => {
    const mine = isEmployer && state.userId === userId ? state : NOOP_ONBOARDING
    return {
      loaded: mine.loaded,
      tourStatus: mine.tourStatus,
      completedSteps: mine.completedSteps,
      checklistDismissed: mine.checklistDismissed,
      markStep,
      finishTour,
      dismissChecklist,
    }
  }, [state, isEmployer, userId, markStep, finishTour, dismissChecklist])

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>
}
