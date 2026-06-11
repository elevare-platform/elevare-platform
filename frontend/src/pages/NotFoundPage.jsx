import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import ehsLogo from '@/assets/ehs-logo.png'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <>
      <Helmet>
        <title>Page Not Found | Elevare Human Solutions</title>
        <meta name="robots" content="noindex" />
      </Helmet>
      <main className="min-h-screen bg-[#fafbfc] flex flex-col items-center justify-center px-4 text-center">
        <Link to="/" className="mb-8">
          <img src={ehsLogo} alt="Elevare Human Solutions" width={140} height={48} className="h-12 w-auto mx-auto" />
        </Link>

        <p className="text-8xl font-extrabold text-brand-blue mb-4">404</p>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-text mb-3">Page not found</h1>
        <p className="text-sm text-text-muted max-w-sm mb-10">
          The page you're looking for doesn't exist or has been moved.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <Link to="/">
            <Button className="bg-brand-blue hover:bg-brand-blue/90 text-white border-0 px-8 rounded-full font-bold text-sm uppercase tracking-wider">
              Back to Homepage
            </Button>
          </Link>
          <Link to="/jobs">
            <Button variant="outline" className="px-8 rounded-full font-bold text-sm uppercase tracking-wider border-brand-blue text-brand-blue hover:bg-brand-blue-light inline-flex items-center gap-2">
              <Search size={15} /> Browse Jobs
            </Button>
          </Link>
        </div>
      </main>
      <FloatingWhatsApp />
    </>
  )
}
