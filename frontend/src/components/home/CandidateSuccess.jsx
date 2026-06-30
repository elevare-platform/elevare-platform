import { useState, useEffect } from 'react'
import { Briefcase, TrendingUp, GraduationCap, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

const CARDS = [
  {
    icon: Briefcase,
    title: 'Unrivaled Job Opportunities',
    subtitle: 'Step into career-defining roles',
    description: 'We connect you directly with Nigeria’s leading companies, hyper-growth startups, and multinational brands. Skip the recruiter black hole and get your profile reviewed instantly.',
    image: '/hero-images/img23.jpg',
    tag: 'PLACEMENTS',
    accentColor: '#1A4D8F',
  },
  {
    icon: TrendingUp,
    title: 'Accelerated Career Growth',
    subtitle: 'Long-term path mapping',
    description: 'We don’t just place you in a job; we guide your career trajectory. 87% of our placed candidates report receiving promotions or expanded responsibilities within 12 months.',
    image: '/hero-images/img24.jpg',
    tag: 'CAREER PATHS',
    accentColor: '#E87722',
  },
  {
    icon: GraduationCap,
    title: 'Professional Development',
    subtitle: 'Upskill & stay competitive',
    description: 'Access exclusive bootcamps, resume-polishing bootcamps, and technical skills validation workshops led by industry leaders. Make your expertise impossible to ignore.',
    image: '/hero-images/img25.jpg',
    tag: 'UPSKILLING',
    accentColor: '#10b981',
  },
]

export default function CandidateSuccess() {
  const [activeIndex, setActiveIndex] = useState(0)
  const [isFading, setIsFading] = useState(false)

  // Auto-transition slides every 8 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      handleIndexChange((activeIndex + 1) % CARDS.length)
    }, 8000)
    return () => clearInterval(timer)
  }, [activeIndex])

  const handleIndexChange = (index) => {
    if (index === activeIndex) return
    setIsFading(true)
    setTimeout(() => {
      setActiveIndex(index)
      setIsFading(false)
    }, 350)
  }

  return (
    <section
      aria-label="Candidate Success Showcase"
      className="relative py-24 sm:py-32 overflow-hidden bg-slate-50 text-text"
    >
      {/* Ambient background decoration */}
      <div className="absolute top-0 left-0 w-80 h-80 bg-brand-blue/5 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-brand-amber/5 rounded-full blur-[120px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 sm:px-8 lg:px-12 relative z-10">
        
        {/* Header */}
        <div className="mb-16 md:mb-20 max-w-3xl">
          <span className="text-xs font-extrabold uppercase tracking-widest text-brand-amber bg-brand-amber/10 px-4 py-1.5 rounded-full border border-brand-amber/20">
            For Candidates
          </span>
          <h2
            className="text-4xl sm:text-5xl font-extrabold mt-6 tracking-tight text-slate-900 leading-tight"
            style={{ fontFamily: "'Lobster Two', cursive" }}
          >
            Empowering Your Professional Journey
          </h2>
          <p className="mt-4 text-text-muted text-base sm:text-lg max-w-xl">
            We provide candidates with the jobs, matching support, and training needed to land dream jobs and scale their careers in Africa.
          </p>
        </div>

        {/* Dynamic Display Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          
          {/* Left Column: Interactive Cards Stack */}
          <div className="lg:col-span-6 flex flex-col gap-6 order-2 lg:order-1">
            {CARDS.map((card, idx) => {
              const IconComp = card.icon
              const isActive = activeIndex === idx
              
              return (
                <div
                  key={idx}
                  onClick={() => handleIndexChange(idx)}
                  className={`relative flex gap-5 p-6 rounded-2xl cursor-pointer transition-all duration-300 border text-left ${
                    isActive
                      ? 'bg-white border-slate-200 shadow-xl scale-[1.02]'
                      : 'bg-transparent border-transparent hover:bg-white/50 hover:border-slate-100'
                  }`}
                >
                  {/* Left Accent indicator line */}
                  <div
                    className="absolute left-0 top-0 bottom-0 w-1.5 rounded-l-2xl transition-all duration-300"
                    style={{
                      backgroundColor: card.accentColor,
                      opacity: isActive ? 1 : 0,
                    }}
                  />

                  {/* Icon Box */}
                  <div
                    className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                      isActive ? 'text-white' : 'bg-slate-200/60 text-slate-600'
                    }`}
                    style={{
                      backgroundColor: isActive ? card.accentColor : undefined,
                    }}
                  >
                    <IconComp className="w-6 h-6" />
                  </div>

                  {/* Card content */}
                  <div>
                    <span className="text-[10px] font-extrabold tracking-widest text-slate-400 uppercase">
                      {card.tag}
                    </span>
                    <h3 className="text-lg font-bold text-slate-900 mt-1 transition-colors">
                      {card.title}
                    </h3>
                    <p className={`mt-2 text-xs sm:text-sm leading-relaxed transition-opacity duration-300 ${
                      isActive ? 'text-text-muted' : 'text-slate-500 line-clamp-2'
                    }`}>
                      {card.description}
                    </p>

                    {isActive && (
                      <div className="mt-4 flex items-center gap-2 animate-fade-in-up">
                        <Link to="/jobs">
                          <Button size="sm" className="bg-brand-blue hover:bg-brand-blue-dark text-white rounded-md text-xs py-1 h-8">
                            Explore Opportunities <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                          </Button>
                        </Link>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Right Column: Visual Showcase (Images) with transition */}
          <div className="lg:col-span-6 order-1 lg:order-2">
            <div className="relative aspect-video sm:aspect-square lg:aspect-[4/3] rounded-3xl overflow-hidden shadow-2xl bg-slate-200">
              
              {/* Image Transition Layers */}
              {CARDS.map((card, idx) => (
                <div
                  key={idx}
                  className={`absolute inset-0 bg-cover bg-center transition-all duration-700 ease-in-out ${
                    idx === activeIndex
                      ? 'opacity-100 scale-100 rotate-0'
                      : 'opacity-0 scale-105 rotate-1 pointer-events-none'
                  }`}
                  style={{
                    backgroundImage: `url(${card.image})`,
                  }}
                />
              ))}

              {/* Tint overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-slate-900/60 via-slate-900/10 to-transparent pointer-events-none" />

              {/* Tag/Badge display inside the photo */}
              <div className="absolute bottom-6 left-6 right-6 bg-white/95 backdrop-blur-md p-6 rounded-2xl border border-white/20 shadow-xl flex items-center justify-between z-20">
                <div>
                  <p className="text-[10px] font-extrabold uppercase tracking-widest text-brand-amber">
                    {CARDS[activeIndex].tagline || 'HIGHLIGHT'}
                  </p>
                  <p className="text-sm sm:text-base font-extrabold text-slate-900 mt-1">
                    {CARDS[activeIndex].subtitle}
                  </p>
                </div>
                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>
    </section>
  )
}
