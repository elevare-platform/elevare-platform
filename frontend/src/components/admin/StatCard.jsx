import { useEffect, useRef, useState } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

function useCountUp(target, duration = 800) {
  const [count, setCount] = useState(0)
  const raf = useRef(null)

  useEffect(() => {
    if (target === 0) { setCount(0); return }
    const start = performance.now()
    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1)
      setCount(Math.floor(progress * target))
      if (progress < 1) raf.current = requestAnimationFrame(animate)
      else setCount(target)
    }
    raf.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])

  return count
}

export default function StatCard({ label, value, trend, trendLabel, icon: Icon }) {
  const displayed = useCountUp(value ?? 0)

  const TrendIcon =
    trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus
  const trendColor =
    trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-500' : 'text-text-muted'

  return (
    <div className="bg-white rounded-xl border border-border p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-muted font-medium">{label}</p>
        {Icon && <Icon size={18} className="text-text-muted" aria-hidden="true" />}
      </div>
      <p className="text-3xl font-bold text-text tabular-nums">{displayed.toLocaleString()}</p>
      {trendLabel && (
        <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
          <TrendIcon size={13} aria-hidden="true" />
          <span>{trendLabel}</span>
        </div>
      )}
    </div>
  )
}
