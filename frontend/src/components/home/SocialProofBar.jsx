import GourmetTwistLogo from './GourmetTwistLogo'

// ─── Company logos ────────────────────────────────────────────────────────
const COMPANIES = [
  { name: 'EL-Rishon Logistics', logo: 'https://www.elrishonlogistics.com/m/wp-content/uploads/2024/06/el-rishon-logo.png' },
  { name: 'Kid City Lagos', logo: 'https://www.kidcity.ng/wp-content/uploads/2026/02/KIDCITY-LOGO.png' },
  { name: 'Limeswood International', logo: 'https://limeswood.com.ng/wp-content/uploads/2024/06/LIMESWOOD-LOGO-.png' },
  { name: 'Gourmet Twist', logo: 'svg' },
  { name: 'Goldplates Feast House', logo: 'https://goldplatesfeasthouse.com/wp-content/uploads/2023/10/cropped-cropped-GoldPlates.png' },
  { name: 'The Gardens Ikoyi', logo: 'https://thegardenikoyi.com/wp-content/uploads/2024/07/WhatsApp-Image-2025-08-05-at-16.58.49.jpeg' },
  { name: 'Springpet Homes', logo: 'https://springpethomes.com/wp-content/uploads/2024/02/SP-NEW-LOGO-white.png', isWhite: true },
  { name: 'Homiva Property Ventures', logo: 'https://scontent.cdninstagram.com/v/t51.2885-19/11355715_1138391279509010_1218021382_a.jpg?stp=dst-jpg_s150x150_tt6&_nc_cat=107&ccb=7-5&_nc_sid=f7ccc5&efg=eyJ2ZW5jb2RlX3RhZyI6InByb2ZpbGVfcGljLnd3dy40OTMuQzMifQ%3D%3D&_nc_ohc=qBCpRnPNNQoQ7kNvwH6hTQ1&_nc_oc=AdpiWNqj7iycZuyqDGN2FsYyFQEKx5X81QqgKKZELeWPo3fYiSRmficWazydRSf6kyk&_nc_zt=24&_nc_ht=scontent.cdninstagram.com&_nc_ss=7ba8c&oh=00_AQC3TJqGVx913nZR9Rheh-b8knI_ZeYCXv5Lgq-v0XLjBw&oe=6A4D56B1' },
  { name: 'Jolly Energy Fleet', logo: 'https://jollyenergyfleet.com/wp-content/uploads/JEF-logo-white-bg-e1731497932559.png' },
  { name: 'Health Bridge Medical Center', logo: 'http://healthbridgemc.com/wp-content/uploads/2017/04/logoweb2.png' },
  { name: 'The Smiths Group', logo: 'https://scontent.cdninstagram.com/v/t51.2885-19/470042214_454856731007855_6597041336044451919_n.jpg?stp=dst-jpg_s150x150_tt6&_nc_cat=104&ccb=7-5&_nc_sid=f7ccc5&efg=eyJ2ZW5jb2RlX3RhZyI6InByb2ZpbGVfcGljLnd3dy44MDAuQzMifQ%3D%3D&_nc_ohc=n122gBplSPAQ7kNvwGZKdfQ&_nc_oc=Adpb2W736Us_tNYAxlbu-t4XWrqQd979ZHN6_anVbLeOZ-UsxVLsduxEnAH9LLTchxE&_nc_zt=24&_nc_ht=scontent.cdninstagram.com&_nc_ss=7ba8c&oh=00_AQDAgDRv-bzxe0LOvQA51jIDy4gZ0dq7V6uQMEInlvpgPg&oe=6A4D32FC' },
]

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
          Trusted by 10+ companies
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
              alignItems: 'center'
            }}
          >
            {[...COMPANIES, ...COMPANIES].map((company, i) => (
              <div key={i} className={`flex items-center justify-center opacity-80 hover:opacity-100 transition-opacity ${company.isWhite ? 'invert' : ''}`} title={company.name}>
                {company.logo === 'svg' ? (
                  <GourmetTwistLogo style={{ height: '36px', width: 'auto' }} />
                ) : (
                  <img src={company.logo} alt={company.name} style={{ height: '36px', width: 'auto', objectFit: 'contain' }} className="max-w-[120px]" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
