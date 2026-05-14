import { useEffect, useRef, useState } from 'react'

/**
 * useIntersectionObserver
 * @param {Object} options
 * @param {number} [options.threshold=0.1] - Intersection threshold (0–1)
 * @param {boolean} [options.triggerOnce=false] - Disconnect after first intersection
 * @returns {[React.RefObject, boolean]} [ref, isVisible]
 */
export function useIntersectionObserver({ threshold = 0.1, triggerOnce = false } = {}) {
  const ref = useRef(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          if (triggerOnce) {
            observer.disconnect()
          }
        } else {
          if (!triggerOnce) {
            setIsVisible(false)
          }
        }
      },
      { threshold }
    )

    observer.observe(element)

    return () => {
      observer.disconnect()
    }
  }, [threshold, triggerOnce])

  return [ref, isVisible]
}
