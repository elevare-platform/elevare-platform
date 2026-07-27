import { useEffect, useState, useRef } from 'react'
import { useInView } from 'framer-motion'

export default function AnimatedCounter({
  target,
  duration = 1800,
  prefix = '',
  suffix = '',
  decimals = 0,
  liveTick = false,
  className = '',
}) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, amount: 0.3 })
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (!isInView) return

    let startTime = null
    let animationFrame = null

    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      // Ease out cubic
      const easedProgress = 1 - Math.pow(1 - progress, 3)
      setCount(easedProgress * target)

      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate)
      } else {
        setCount(target)
      }
    }

    animationFrame = requestAnimationFrame(animate)

    return () => {
      if (animationFrame) cancelAnimationFrame(animationFrame)
    }
  }, [isInView, target, duration])

  // Periodic subtle live tick-up to give an "alive" feeling to graph candidate counts
  useEffect(() => {
    if (!liveTick || !isInView) return

    const interval = setInterval(() => {
      setCount((prev) => prev + Math.floor(Math.random() * 3) + 1)
    }, 4500)

    return () => clearInterval(interval)
  }, [liveTick, isInView])

  const formattedNumber =
    decimals > 0
      ? count.toFixed(decimals)
      : Math.floor(count).toLocaleString()

  return (
    <span ref={ref} className={`inline-block tabular-nums ${className}`}>
      {prefix}
      {formattedNumber}
      {suffix}
    </span>
  )
}
