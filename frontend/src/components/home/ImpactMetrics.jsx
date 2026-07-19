import { useEffect, useRef, useState } from 'react'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'
import { Users, Building2, Calendar, Target } from 'lucide-react'

const METRICS = [
  {
    icon: Users,
    value: 12450,
    suffix: '+',
    label: 'Candidates Placed',
    description: 'Empowered professionals matching career aspirations across Africa.',
    color: '#E87722',
  },
  {
    icon: Building2,
    value: 480,
    suffix: '+',
    label: 'Clients Served',
    description: 'Companies successfully scaling their operations with our talent pipelines.',
    color: '#1A4D8F',
  },
  {
    icon: Calendar,
    value: 12,
    suffix: '+ years',
    label: 'Years Experience',
    description: 'Of deep regional presence, technical recruitment expertise, and ecosystem trust.',
    color: '#10b981',
  },
  {
    icon: Target,
    value: 24,
    suffix: '+',
    label: 'Industries Supported',
    description: 'From fintech and logistics to retail, banking, and hyper-growth tech.',
    color: '#8b5cf6',
  },
]

function useCounter(target, duration, isActive) {
  const [count, setCount] = useState(0)
  const startTime = useRef(null)
  const raf = useRef(null)

  useEffect(() => {
    if (!isActive) return

    startTime.current = null

    function animate(timestamp) {
      if (!startTime.current) startTime.current = timestamp
      const elapsed = timestamp - startTime.current
      const progress = Math.min(elapsed / duration, 1)
      
      // Easing out function
      const easeOutQuad = (t) => t * (2 - t)
      const currentVal = Math.floor(easeOutQuad(progress) * target)
      
      setCount(currentVal)

      if (progress < 1) {
        raf.current = requestAnimationFrame(animate)
      } else {
        setCount(target)
      }
    }

    raf.current = requestAnimationFrame(animate)

    return () => {
      if (raf.current) cancelAnimationFrame(raf.current)
    }
  }, [isActive, target, duration])

  return count
}

function MetricCard({ metric, isActive }) {
  const count = useCounter(metric.value, 2000, isActive)
  const Icon = metric.icon

  return (
    <div
      className="glass-panel-dark premium-card relative rounded-2xl p-8 border border-white/10 flex flex-col justify-between overflow-hidden group"
      style={{
        background: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(12px)',
        minHeight: '230px',
      }}
    >
      {/* Background glow node */}
      <div
        className="absolute -top-12 -right-12 w-24 h-24 rounded-full blur-[40px] opacity-15 group-hover:opacity-30 transition-opacity duration-500"
        style={{ backgroundColor: metric.color }}
      />

      {/* Top section: Icon and dynamic glow outline */}
      <div className="flex items-center justify-between mb-6">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center text-white transition-all duration-300 group-hover:scale-110"
          style={{
            backgroundColor: `${metric.color}20`,
            border: `1px solid ${metric.color}40`,
            color: metric.color
          }}
        >
          <Icon className="w-5 h-5" />
        </div>
        <span className="text-[10px] font-bold text-slate-500 tracking-widest uppercase">
          METRIC
        </span>
      </div>

      {/* Value counter */}
      <div>
        <p className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-none mb-3">
          {count.toLocaleString()}
          <span
            className="text-2xl font-bold ml-1"
            style={{ color: metric.color }}
          >
            {metric.suffix}
          </span>
        </p>
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-2">
          {metric.label}
        </h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          {metric.description}
        </p>
      </div>
    </div>
  )
}

export default function ImpactMetrics() {
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.15, triggerOnce: true })

  return (
    <section
      ref={sectionRef}
      aria-label="Platform Impact Metrics"
      className="relative py-24 sm:py-32 overflow-hidden bg-slate-950"
    >
      {/* Background elements */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-brand-blue/5 rounded-full blur-[160px] pointer-events-none" />
      <div className="absolute inset-0 brand-panel-grid opacity-5 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 sm:px-8 lg:px-12 relative z-10">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16 sm:mb-20">
          <span className="text-xs font-extrabold uppercase tracking-widest text-brand-amber bg-brand-amber/10 px-4 py-1.5 rounded-full border border-brand-amber/20">
            Platform Impact
          </span>
          <h2
            className="font-sans text-4xl sm:text-5xl font-extrabold mt-6 tracking-tight text-white leading-tight"
          >
            Metrics That Validate Excellence
          </h2>
          <p className="mt-4 text-slate-400 text-base sm:text-lg max-w-xl mx-auto">
            Our platform numbers prove the value and trust that we bring to Africa's recruitment and human capital landscape.
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
          {METRICS.map((metric, idx) => (
            <MetricCard key={idx} metric={metric} isActive={isVisible} />
          ))}
        </div>

      </div>
    </section>
  )
}
