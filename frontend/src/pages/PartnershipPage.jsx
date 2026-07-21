import { useState } from 'react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import {
  Briefcase,
  Users,
  CheckCircle2,
  PhoneCall,
  Sparkles,
  Award,
  Layers,
  ArrowRight,
} from 'lucide-react'

export default function PartnershipPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [formSubmitted, setFormSubmitted] = useState(false)
  const [formData, setFormData] = useState({
    companyName: '',
    contactPerson: '',
    email: '',
    hiringNeeds: 'Recruitment Partnership',
    message: '',
  })

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleFormSubmit = (e) => {
    e.preventDefault()
    // Mock successful submission
    setFormSubmitted(true)
    setFormData({
      companyName: '',
      contactPerson: '',
      email: '',
      hiringNeeds: 'Recruitment Partnership',
      message: '',
    })
  }

  return (
    <>
      <Navbar onBookConsultation={openModal} />

      <main className="pt-16 bg-[#fafbfc] min-h-screen">
        
        {/* 1. Header Section */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ backgroundImage: "url('/hero-images/img18.jpg')" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                <Award size={14} /> Corporate B2B Programs
              </span>
              <h1 className="font-sans text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight">
                Recruitment &amp; Outsourcing Partnership
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-2xl">
                Forming strategic hiring alliances and providing compliant workforce outsourcing solutions to optimize payroll efficiency, legal coverage, and staff performance.
              </p>
              <div className="flex flex-wrap gap-3 pt-2">
                <Button onClick={openModal} className="bg-brand-amber hover:bg-brand-amber-dark text-white font-bold text-sm px-6 py-3 border-0 shadow-lg hover:scale-[1.02] transition-transform">
                  Book B2B Consultation
                </Button>
                <a href="#partnership-form" className="bg-white/10 border border-white/20 hover:bg-white/20 text-white font-bold text-sm px-6 py-3 rounded transition-colors flex items-center gap-2">
                  Partner With Us <ArrowRight size={16} />
                </a>
              </div>
            </div>
          </div>
          <div className="curve-divider-bottom" style={{ height: '3vw' }}>
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
              <path d="M0,64L120,80C240,96,480,128,720,128C960,128,1200,96,1320,80L1440,64L1440,120L1320,120C1200,120,960,120,720,120C480,120,240,120,120,120L0,120Z" fill="#fafbfc" />
            </svg>
          </div>
        </section>

        {/* 2. Partnership Features Section */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
            
            {/* Left: Overview Content */}
            <div className="lg:col-span-6 space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-blue-light text-brand-blue text-xs font-bold uppercase tracking-wider">
                <Briefcase size={14} /> Enterprise Operations
              </span>
              <h2 className="text-3xl font-extrabold text-text leading-tight">
                Aligning Corporate Vision with Strategic Hiring Solutions
              </h2>
              <p className="text-text-muted text-base leading-relaxed">
                Elevare Human Solutions Ltd provides robust, scalable talent models. From full-lifecycle contract outsourcing to high-caliber executive recruiting partnerships, we co-manage recruitment structures so you can focus on core growth.
              </p>

              <div className="space-y-4">
                {[
                  {
                    title: 'Strategic Talent Sourcing Partnerships',
                    desc: 'Ongoing access to our executive network database, direct-hire mapping, and retained searches.',
                  },
                  {
                    title: 'Compliant Outsourcing Frameworks',
                    desc: 'Contract staffing management, payroll administration oversight, legal coverage, and employee handbooks.',
                  },
                  {
                    title: 'Tailored B2B Consultation Services',
                    desc: 'Expert workforce diagnostics, competency-mapping reviews, and organizational audits.',
                  },
                ].map((item, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-blue-light text-brand-blue flex items-center justify-center mt-0.5">
                      <CheckCircle2 size={16} />
                    </div>
                    <div>
                      <h3 className="font-bold text-text text-sm sm:text-base">{item.title}</h3>
                      <p className="text-text-muted text-xs sm:text-sm mt-0.5">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Interactive Partnership Inquiry Form */}
            <div id="partnership-form" className="lg:col-span-6">
              <div className="bg-white p-6 sm:p-8 rounded-2xl border border-border shadow-xl">
                <h3 className="text-xl font-extrabold text-text mb-2">Corporate Inquiry Form</h3>
                <p className="text-text-muted text-xs mb-6">
                  Tell us about your organization's hiring parameters. Our senior strategic consultant will follow up within 24 business hours.
                </p>

                {formSubmitted ? (
                  <div className="p-6 bg-green-500/10 border border-green-500/20 text-center rounded-xl space-y-3">
                    <CheckCircle2 size={36} className="text-green-500 mx-auto" />
                    <h4 className="font-extrabold text-text text-base">Inquiry Submitted Successfully</h4>
                    <p className="text-text-muted text-xs leading-relaxed">
                      Thank you for contacting Elevare. A B2B strategist will review your hiring profile and contact you immediately.
                    </p>
                    <Button onClick={() => setFormSubmitted(false)} size="sm" variant="outline" className="mt-2">
                      Submit Another Inquiry
                    </Button>
                  </div>
                ) : (
                  <form onSubmit={handleFormSubmit} className="space-y-4">
                    <div>
                      <label className="block text-xs uppercase tracking-wider font-extrabold text-text mb-1.5">
                        Company Name
                      </label>
                      <input
                        type="text"
                        name="companyName"
                        required
                        placeholder="e.g. Acme Corp"
                        value={formData.companyName}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2.5 bg-white border border-border rounded focus:border-brand-blue text-sm focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs uppercase tracking-wider font-extrabold text-text mb-1.5">
                        Contact Person
                      </label>
                      <input
                        type="text"
                        name="contactPerson"
                        required
                        placeholder="e.g. John Doe"
                        value={formData.contactPerson}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2.5 bg-white border border-border rounded focus:border-brand-blue text-sm focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs uppercase tracking-wider font-extrabold text-text mb-1.5">
                        Work Email
                      </label>
                      <input
                        type="email"
                        name="email"
                        required
                        placeholder="e.g. j.doe@acme.com"
                        value={formData.email}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2.5 bg-white border border-border rounded focus:border-brand-blue text-sm focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs uppercase tracking-wider font-extrabold text-text mb-1.5">
                        Hiring Needs
                      </label>
                      <select
                        name="hiringNeeds"
                        value={formData.hiringNeeds}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2.5 bg-white border border-border rounded focus:border-brand-blue text-sm focus:outline-none"
                      >
                        <option value="Recruitment Partnership">Recruitment Partnership</option>
                        <option value="Staff Outsourcing Services">Staff Outsourcing Services</option>
                        <option value="Both Recruitment & Outsourcing">Both Recruitment &amp; Outsourcing</option>
                        <option value="Workforce Consulting/Advisory">Workforce Consulting/Advisory</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs uppercase tracking-wider font-extrabold text-text mb-1.5">
                        Message / Scope details
                      </label>
                      <textarea
                        name="message"
                        required
                        rows={3}
                        placeholder="Describe headcount metrics, job titles, or compliance objectives..."
                        value={formData.message}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2.5 bg-white border border-border rounded focus:border-brand-blue text-sm focus:outline-none"
                      />
                    </div>

                    <Button type="submit" className="w-full py-3 bg-brand-blue hover:bg-brand-blue-dark text-white font-bold text-sm shadow">
                      Partner With Us
                    </Button>
                  </form>
                )}
              </div>
            </div>

          </div>
        </section>

      </main>

      <Footer onBookConsultation={openModal} />
      <ConsultationModal isOpen={isModalOpen} onClose={closeModal} />
      <FloatingWhatsApp />
    </>
  )
}
