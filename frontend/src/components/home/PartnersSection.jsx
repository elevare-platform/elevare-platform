import { COMPANIES, GourmetTwistLogo } from './companies'

export default function PartnersSection() {
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

        {/* Responsive Grid with actual logos */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 items-center justify-center max-w-5xl mx-auto">
          {COMPANIES.map((partner, idx) => (
            <div
              key={idx}
              className="group flex flex-col items-center justify-center p-6 bg-surface-muted rounded-xl border border-border/80 transition-all duration-300 hover:border-brand-blue/20 hover:shadow-sm"
            >
              <div
                className="h-16 w-full flex items-center justify-center mb-3"
                style={partner.isDark ? {
                  background: '#1e293b',
                  borderRadius: '8px',
                  padding: '8px',
                } : undefined}
              >
                {partner.logo === 'svg' ? (
                  <GourmetTwistLogo className="h-full w-auto opacity-80 group-hover:opacity-100 transition-opacity" />
                ) : partner.logo === null ? (
                  <span className="text-sm font-bold text-text text-center leading-tight">
                    {partner.name}
                  </span>
                ) : (
                  <img
                    src={partner.logo}
                    alt={partner.name}
                    className={`max-h-full max-w-full object-contain opacity-80 group-hover:opacity-100 transition-opacity ${partner.isWhite ? 'invert' : ''}`}
                  />
                )}
              </div>
              <p className="text-xs font-bold text-slate-500 text-center group-hover:text-text transition-colors">
                {partner.name}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
