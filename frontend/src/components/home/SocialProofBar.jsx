import { COMPANIES, GourmetTwistLogo } from './companies'

export default function SocialProofBar() {
  return (
    <section
      aria-label="Trusted companies"
      style={{
        background: '#ffffff',
        borderTop: '1px solid #E5E7EB',
        borderBottom: '1px solid #E5E7EB',
        padding: '16px 0',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          maxWidth: '80rem',
          margin: '0 auto',
          padding: '0 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '2rem',
        }}
      >
        <p
          style={{
            flexShrink: 0,
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: '#64748b',
            whiteSpace: 'nowrap',
          }}
        >
          Trusted by 19+ companies
        </p>

        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            WebkitMaskImage:
              'linear-gradient(to right, transparent 0%, black 8%, black 92%, transparent 100%)',
            maskImage:
              'linear-gradient(to right, transparent 0%, black 8%, black 92%, transparent 100%)',
          }}
        >
          <div
            className="animate-scroll-x"
            style={{
              display: 'flex',
              gap: '4rem',
              width: 'max-content',
              alignItems: 'center',
            }}
          >
            {[...COMPANIES, ...COMPANIES].map((company, i) => (
              <div
                key={i}
                className="flex items-center justify-center opacity-80 hover:opacity-100 transition-opacity"
                title={company.name}
                style={company.isDark ? {
                  background: '#1e293b',
                  borderRadius: '6px',
                  padding: '4px 8px',
                } : undefined}
              >
                {company.logo === 'svg' ? (
                  <GourmetTwistLogo style={{ height: '36px', width: 'auto' }} />
                ) : company.logo === null ? (
                  <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: company.isDark ? '#f1f5f9' : '#1e293b', whiteSpace: 'nowrap', letterSpacing: '0.02em' }}>
                    {company.name}
                  </span>
                ) : (
                  <img
                    src={company.logo}
                    alt={company.name}
                    style={{ height: '36px', width: 'auto', objectFit: 'contain' }}
                    className={`max-w-[120px] ${company.isWhite ? 'invert' : ''}`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
