import { useState, useEffect, useRef } from 'react'
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router-dom'

const SLIDES = [
  {
    image: '/hero-images/img8.jpg',
    headline: 'Connecting Great Talent With Great Employers',
    text: "We bridge the gap between Africa's top professional talent and ambitious organizations ready to scale.",
    ctaText: 'Find Top Talent',
    ctaLink: '/register?type=employer',
  },
  {
    image: '/hero-images/img16.jpg',
    headline: 'AI-Powered Recruitment That Saves Time',
    text: 'Our intelligent matching technology filters and pre-vets candidates, delivering the top 5% profiles in record time.',
    ctaText: 'Explore AI Matching',
    ctaLink: '/services',
  },
  {
    image: '/hero-images/img18.jpg',
    headline: 'Workforce Solutions Designed For Growth',
    text: 'From payroll administration to HR compliance, we handle the operational details so your team can focus on execution.',
    ctaText: 'See Services',
    ctaLink: '/services',
  },
  {
    image: '/hero-images/img27.jpg',
    headline: 'Building Stronger Organizations Across Africa',
    text: 'Creating sustainable, high-performing workforces that drive long-term productivity, compliance, and innovation.',
    ctaText: 'Partner With Us',
    ctaLink: '/partnership',
  },
]

export default function StorySlider() {
  const [current, setCurrent] = useState(0)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const timerRef = useRef(null)

  const resetTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      handleNext()
    }, 6000)
  }

  useEffect(() => {
    resetTimer()
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [current])

  const handleNext = () => {
    if (isTransitioning) return
    setIsTransitioning(true)
    setTimeout(() => {
      setCurrent((prev) => (prev + 1) % SLIDES.length)
      setIsTransitioning(false)
    }, 500)
  }

  const handlePrev = () => {
    if (isTransitioning) return
    setIsTransitioning(true)
    setTimeout(() => {
      setCurrent((prev) => (prev - 1 + SLIDES.length) % SLIDES.length)
      setIsTransitioning(false)
    }, 500)
  }

  const handleDotClick = (index) => {
    if (isTransitioning || index === current) return
    setIsTransitioning(true)
    setTimeout(() => {
      setCurrent(index)
      setIsTransitioning(false)
    }, 500)
  }

  return (
    <section
      aria-label="Elevare Storytelling Slider"
      className="relative w-full h-[600px] md:h-[650px] overflow-hidden bg-slate-950 flex items-center"
    >
      {/* Background Images with Cross-fade */}
      {SLIDES.map((slide, idx) => (
        <div
          key={idx}
          className={`absolute inset-0 bg-cover bg-center transition-all duration-[1500ms] ease-in-out ${
            idx === current ? 'opacity-40 scale-100' : 'opacity-0 scale-105 pointer-events-none'
          }`}
          style={{
            backgroundImage: `url(${slide.image})`,
          }}
        />
      ))}

      {/* Dark Ambient Overlay (gradient) */}
      <div
        className="absolute inset-0 bg-gradient-to-r from-slate-950 via-slate-900/80 to-transparent"
        style={{ pointerEvents: 'none' }}
      />

      {/* Content Container */}
      <div className="relative max-w-7xl mx-auto px-6 sm:px-8 lg:px-12 w-full z-10 text-white">
        <div className="max-w-2xl">
          {/* Tagline / Eyebrow */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1 bg-brand-amber/10 border border-brand-amber/30 rounded-full mb-6">
            <span className="w-2 h-2 rounded-full bg-brand-amber animate-pulse" />
            <span className="text-[10px] sm:text-xs font-semibold tracking-wider text-brand-amber uppercase">
              REDEFINING AFRICA'S FUTURE WORKFORCE
            </span>
          </div>

          {/* Large Title */}
          <h2
            className={`font-sans text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white mb-6 leading-[1.15] transition-all duration-700 ease-out ${
              isTransitioning ? 'opacity-0 translate-y-4' : 'opacity-100 translate-y-0'
            }`}
          >
            {SLIDES[current].headline}
          </h2>

          {/* Subtitle */}
          <p
            className={`text-base sm:text-lg text-slate-300 mb-8 max-w-xl leading-relaxed transition-all duration-700 delay-100 ease-out ${
              isTransitioning ? 'opacity-0 translate-y-4' : 'opacity-100 translate-y-0'
            }`}
          >
            {SLIDES[current].text}
          </p>

          {/* CTA Row */}
          <div
            className={`flex flex-wrap items-center gap-4 transition-all duration-700 delay-200 ease-out ${
              isTransitioning ? 'opacity-0 translate-y-4' : 'opacity-100 translate-y-0'
            }`}
          >
            <Link to={SLIDES[current].ctaLink}>
              <Button
                size="lg"
                className="bg-brand-amber hover:bg-brand-amber-dark text-white border-none font-bold rounded-lg shadow-lg hover:shadow-brand-amber/20 hover:scale-[1.02] transition-all duration-300"
              >
                {SLIDES[current].ctaText} <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
            <Link to="/about">
              <Button
                variant="outline"
                size="lg"
                className="border-white/30 text-white bg-white/5 hover:bg-white/15 backdrop-blur-sm rounded-lg transition-colors duration-300"
              >
                Learn More
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Navigation Arrows */}
      <button
        onClick={handlePrev}
        aria-label="Previous Slide"
        className="absolute left-4 sm:left-6 z-25 p-3 rounded-full bg-slate-900/40 hover:bg-brand-blue border border-white/10 text-white backdrop-blur-sm transition-all hover:scale-105 duration-300"
      >
        <ChevronLeft className="w-5 h-5" />
      </button>
      <button
        onClick={handleNext}
        aria-label="Next Slide"
        className="absolute right-4 sm:right-6 z-25 p-3 rounded-full bg-slate-900/40 hover:bg-brand-blue border border-white/10 text-white backdrop-blur-sm transition-all hover:scale-105 duration-300"
      >
        <ChevronRight className="w-5 h-5" />
      </button>

      {/* Progress Indicators / Dots */}
      <div className="absolute bottom-8 left-0 right-0 z-20 flex justify-center items-center gap-3">
        {SLIDES.map((_, idx) => (
          <button
            key={idx}
            onClick={() => handleDotClick(idx)}
            aria-label={`Go to slide ${idx + 1}`}
            className="relative h-2 rounded-full overflow-hidden transition-all duration-300"
            style={{
              width: idx === current ? '40px' : '8px',
              backgroundColor: idx === current ? 'transparent' : 'rgba(255,255,255,0.3)',
            }}
          >
            {idx === current && (
              <span className="absolute inset-0 bg-brand-amber animate-slider-progress" />
            )}
          </button>
        ))}
      </div>

      {/* Custom Styles for Slider Animations inside index.css or added directly here */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slider-progress {
          from { width: 0%; }
          to { width: 100%; }
        }
        .animate-slider-progress {
          animation: slider-progress 6000ms linear forwards;
        }
      `}} />
    </section>
  )
}
