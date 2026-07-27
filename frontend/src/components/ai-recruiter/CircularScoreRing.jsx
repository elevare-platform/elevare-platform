import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'

export default function CircularScoreRing({ score, size = 64, strokeWidth = 5 }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, amount: 0.5 })

  const radius = (size - strokeWidth * 2) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - ((isInView ? score : 0) / 100) * circumference

  // Color bands with gradient IDs
  let gradientId = 'gradient-amber'
  let textColor = 'text-amber-400'
  let glowColor = 'shadow-amber-500/20'

  if (score >= 85) {
    gradientId = 'gradient-emerald'
    textColor = 'text-emerald-400'
    glowColor = 'shadow-emerald-500/20'
  } else if (score >= 70) {
    gradientId = 'gradient-cyan'
    textColor = 'text-cyan-400'
    glowColor = 'shadow-cyan-500/20'
  }

  return (
    <div
      ref={ref}
      className={`relative flex items-center justify-center rounded-full shadow-lg ${glowColor}`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90 transform">
        <defs>
          <linearGradient id="gradient-emerald" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#34D399" />
            <stop offset="100%" stopColor="#059669" />
          </linearGradient>
          <linearGradient id="gradient-cyan" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="100%" stopColor="#1A4D8F" />
          </linearGradient>
          <linearGradient id="gradient-amber" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FBBF24" />
            <stop offset="100%" stopColor="#E87722" />
          </linearGradient>
        </defs>

        {/* Track background */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255, 255, 255, 0.1)"
          strokeWidth={strokeWidth}
          fill="transparent"
        />

        {/* Animated fill ring */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={`url(#${gradientId})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          fill="transparent"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>

      {/* Center text score */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-sm font-extrabold tracking-tight ${textColor}`}>
          {Math.round(score)}%
        </span>
        <span className="text-[9px] font-bold text-white/50 uppercase tracking-widest leading-none">
          Match
        </span>
      </div>
    </div>
  )
}
