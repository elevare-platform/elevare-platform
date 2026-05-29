import { Sparkles, HelpCircle } from 'lucide-react'

export default function PartnersSection() {
  const PARTNER_PLACEHOLDERS = [
    'EL-Rishon Logistics',
    'Kid City Lagos',
    'Limeswood International',
    'Gourmet Twist',
    'Goldplates Feast House',
    'Springpet Homes',
  ]

  return (
    <section
      aria-label="Official Partners"
      className="bg-white border-y border-border py-16 sm:py-20 overflow-hidden"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center mb-12">
          <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">
            COLLABORATION &amp; TRUST
          </p>
          <h2 className="text-3xl font-extrabold text-text tracking-tight">
            Trusted By Our Partners
          </h2>
          <p className="text-text-muted text-sm max-w-md mx-auto mt-2">
            We partner with forward-thinking enterprises, logistics hubs, and retail groups to co-develop modern HR ecosystems.
          </p>
        </div>

        {/* Responsive Grid with subtle grayscale logo styles */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 items-center justify-center max-w-5xl mx-auto">
          {PARTNER_PLACEHOLDERS.map((partner, idx) => (
            <div
              key={idx}
              className="group flex flex-col items-center justify-center p-6 bg-surface-muted rounded-xl border border-border/80 transition-all duration-300 hover:border-brand-blue/20 hover:shadow-sm"
            >
              {/* Logo Mock Symbol */}
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 group-hover:bg-brand-blue-light group-hover:text-brand-blue transition-colors duration-300">
                <Sparkles size={18} />
              </div>
              <p className="text-xs font-bold text-slate-500 text-center mt-3 group-hover:text-text transition-colors">
                {partner}
              </p>
            </div>
          ))}
        </div>

        {/* Coming Soon Notice (Req 6) */}
        <div className="flex items-center justify-center gap-2 mt-10 text-xs font-semibold text-text-muted bg-surface-muted border border-border px-4 py-2 rounded-full w-max mx-auto shadow-sm">
          <HelpCircle size={14} className="text-brand-amber animate-pulse" />
          <span>Official partner logos coming soon.</span>
        </div>

      </div>
    </section>
  )
}
