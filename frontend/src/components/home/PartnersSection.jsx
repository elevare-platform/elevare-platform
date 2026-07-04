import GourmetTwistLogo from './GourmetTwistLogo'

export default function PartnersSection() {
  const PARTNERS = [
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
          {PARTNERS.map((partner, idx) => (
            <div
              key={idx}
              className="group flex flex-col items-center justify-center p-6 bg-surface-muted rounded-xl border border-border/80 transition-all duration-300 hover:border-brand-blue/20 hover:shadow-sm"
            >
              <div className="h-16 w-full flex items-center justify-center mb-3">
                {partner.logo === 'svg' ? (
                  <GourmetTwistLogo className="h-full w-auto opacity-80 group-hover:opacity-100 transition-opacity" />
                ) : (
                  <img src={partner.logo} alt={partner.name} className={`max-h-full max-w-full object-contain opacity-80 group-hover:opacity-100 transition-opacity ${partner.isWhite ? 'invert' : ''}`} />
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
