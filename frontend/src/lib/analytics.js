/**
 * Analytics helper — wraps react-ga4 so all calls are no-ops when
 * VITE_GA4_ID is not set (local dev without the env var, CI, etc.)
 */
import ReactGA from 'react-ga4'

const ID = import.meta.env.VITE_GA4_ID

export function initAnalytics() {
  if (!ID) return
  ReactGA.initialize(ID)
}

export function trackPageview(path) {
  if (!ID) return
  ReactGA.send({ hitType: 'pageview', page: path })
}

export function trackEvent(category, action, label) {
  if (!ID) return
  ReactGA.event({ category, action, ...(label !== undefined && { label: String(label) }) })
}
