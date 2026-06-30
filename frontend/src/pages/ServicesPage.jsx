import { useState } from 'react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import {
  Users,
  Search,
  UserCheck,
  DollarSign,
  Layers,
  Award,
  Cpu,
  Activity,
  Clock,
  ShieldCheck,
  FileText,
  UserPlus,
  TrendingUp,
  GraduationCap,
  BarChart3,
  Briefcase,
  CheckCircle2,
  ArrowRight,
  ChevronDown,
  Building,
} from 'lucide-react'

// ─── Complete 16 Services list ───────────────────────────────────────────────
const SERVICES_DATA = [
  // Category 1: Talent & Recruitment (4 services)
  {
    id: 'recruitment-executive-search',
    category: 'talent',
    icon: Search,
    name: 'Recruitment & Executive Search',
    description: 'End-to-end recruitment and C-suite placements powered by our extensive professional networks.',
    features: ['Retained & Contingency search', 'Senior leadership mapping', 'Rigorous culture-fit evaluation'],
  },
  {
    id: 'candidate-sourcing-screening',
    category: 'talent',
    icon: UserCheck,
    name: 'Candidate Sourcing & Screening',
    description: 'Advanced automated and manual vetting processes to deliver pre-screened talent pools.',
    features: ['Technical skills testing', 'Behavioral assessment checks', 'Automated reference verification'],
  },
  {
    id: 'employer-branding-solutions',
    category: 'talent',
    icon: Award,
    name: 'Employer Branding Solutions',
    description: 'Developing high-impact strategies to position your organization as an employer of choice.',
    features: ['Employee Value Proposition (EVP)', 'Careers page optimization', 'Social recruitment campaigns'],
  },
  {
    id: 'staff-outsourcing-services',
    category: 'talent',
    icon: Layers,
    name: 'Staff Outsourcing Services',
    description: 'Flexible staffing options and complete workforce management solutions to optimize operations.',
    features: ['Contract staffing', 'Vendor management systems', 'Full HR & Admin coverage'],
  },

  // Category 2: Advisory & Compliance (4 services)
  {
    id: 'hr-consulting-advisory',
    category: 'advisory',
    icon: Users,
    name: 'HR Consulting & Advisory',
    description: 'Strategic guidance on HR policy, organizational structures, and scalable workforce solutions.',
    features: ['Org restructuring', 'Change management roadmap', 'HR audit & diagnostic reviews'],
  },
  {
    id: 'hr-operations-compliance',
    category: 'advisory',
    icon: ShieldCheck,
    name: 'HR Operations & Compliance',
    description: 'Mitigating legal risks and auditing operations to ensure strict adherence to local labor laws.',
    features: ['Labor law audits', 'Disciplinary process management', 'Regulatory filings & reporting'],
  },
  {
    id: 'employee-handbook-development',
    category: 'advisory',
    icon: FileText,
    name: 'Employee Handbook Development',
    description: 'Drafting clear, standardized company handbooks outlining policies, expectations, and culture.',
    features: ['Custom policy design', 'Code of conduct alignment', 'Regular regulatory updates'],
  },
  {
    id: 'business-support-service',
    category: 'advisory',
    icon: Building,
    name: 'Business Support Service',
    description: 'Comprehensive operational support and advisory to streamline non-core enterprise activities.',
    features: ['Facilities management advisory', 'Procurement support solutions', 'Office administration set-up'],
  },

  // Category 3: Workforce Tech & Automation (4 services)
  {
    id: 'workforce-automation-systems',
    category: 'technology',
    icon: Cpu,
    name: 'Workforce Automation Systems',
    description: 'Implementing custom HR systems to automate attendance, leave, performance, and real-time tracking.',
    features: ['SaaS platform implementation', 'Integration with legacy systems', 'Self-service portal setup'],
  },
  {
    id: 'digital-onboarding-systems',
    category: 'technology',
    icon: UserPlus,
    name: 'Digital Onboarding Systems',
    description: 'Providing smooth, modern onboarding experiences that reduce administrative load and accelerate productivity.',
    features: ['Paperless document signing', 'Interactive learning pathways', 'Welcome portal configuration'],
  },
  {
    id: 'performance-management-tracking',
    category: 'technology',
    icon: Activity,
    name: 'Performance Management Tracking',
    description: 'Designing data-driven feedback architectures to evaluate employee contributions objectively.',
    features: ['360-degree reviews', 'Custom competency frameworks', 'Performance improvement roadmaps'],
  },
  {
    id: 'attendance-leave-management',
    category: 'technology',
    icon: Clock,
    name: 'Attendance & Leave Management',
    description: 'Seamless digital tracking systems for leave scheduling, absenteeism logs, and shift coordination.',
    features: ['Geo-fenced attendance check-ins', 'Leave accrual calculations', 'Automated workflow approvals'],
  },

  // Category 4: Performance & Operations (4 services)
  {
    id: 'payroll-management',
    category: 'operations',
    icon: DollarSign,
    name: 'Payroll Management',
    description: 'Accurate, timely, and compliant payroll administration tailored to local labor regulations.',
    features: ['Tax and pension deductions', 'Payslip generation', 'Direct salary disbursement solutions'],
  },
  {
    id: 'kpi-productivity-tracking',
    category: 'operations',
    icon: TrendingUp,
    name: 'KPI & Productivity Tracking',
    description: 'Setting up precise goals and tracking systems to optimize efficiency across all departments.',
    features: ['KPI planning workshops', 'Goal alignment trackers', 'Real-time performance analytics'],
  },
  {
    id: 'corporate-training-programs',
    category: 'operations',
    icon: GraduationCap,
    name: 'Corporate Training Programs',
    description: 'Bespoke upskilling and professional development programs that elevate team capabilities.',
    features: ['Soft skills coaching', 'Leadership incubator courses', 'Role-specific competency classes'],
  },
  {
    id: 'workforce-analytics-reporting',
    category: 'operations',
    icon: BarChart3,
    name: 'Workforce Analytics & Reporting',
    description: 'Leveraging data models to provide business leaders with actionable talent insights and workforce trends.',
    features: ['Attrition root-cause metrics', 'Cost-to-hire calculation logs', 'Demographics & staffing plans'],
  },
]

// ─── FAQ list ────────────────────────────────────────────────────────────────
const FAQS = [
  {
    question: 'How do you customize your HR consulting solutions for different companies?',
    answer: 'We begin with a thorough diagnostic phase, analyzing your current structures, industry regulations, and business goals. Each solution, from employee handbooks to automation setup, is crafted specifically to fit your culture, scale, and compliance requirements.',
  },
  {
    question: 'Can you integrate your workforce automation systems with our existing ERP tools?',
    answer: 'Yes. Our workforce automation systems are fully compatible with industry-leading ERPs, accounting tools, and database suites. We handle the custom configurations and API setups for a completely seamless data flow.',
  },
  {
    question: 'What is the standard onboarding time for staff outsourcing services?',
    answer: 'Contractor and staff outsourcing setups typically take between 5 to 10 business days depending on the volume and job classifications. We handle contract negotiation, insurance setups, compliance filing, and local operations immediately.',
  },
  {
    question: 'How do you ensure payroll compliance with Nigerian tax and pension laws?',
    answer: 'Our dedicated payroll compliance team monitors regulatory updates closely. We automate PAYE, pension scheme calculations, NSITF, ITF, and NHF statutory deductions to ensure 100% compliance with zero penalties.',
  },
]

export default function ServicesPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  const [expandedFaq, setExpandedFaq] = useState(null)

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  // Filter services based on activeTab
  const filteredServices = activeTab === 'all'
    ? SERVICES_DATA
    : SERVICES_DATA.filter((s) => s.category === activeTab)

  return (
    <>
      <Navbar onBookConsultation={openModal} />

      <main className="pt-16 bg-[#fafbfc]">
        {/* ── 1. Premium Hero Header ── */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          {/* Background image from new_images_hero */}
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ 
              backgroundImage: "url('/hero-images/img14.jpg')",
            }}
          />
          {/* Rich Overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-4xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                Enterprise-Grade HR Excellence
              </span>
              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight" style={{ fontFamily: "'Lobster Two', cursive" }}>
                Workforce Transformation &amp; Consulting Services
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-2xl">
                Elevating talent strategy, automating administrative pipelines, and designing robust organizational frameworks that scale.
              </p>

              {/* Trusted Stats banner */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-4xl p-6 bg-white/10 backdrop-blur-md rounded-xl border border-white/15 mt-8">
                <div>
                  <p className="text-2xl sm:text-3xl font-bold text-brand-amber">99%</p>
                  <p className="text-xs text-blue-100 uppercase tracking-wider font-semibold">Placement Accuracy</p>
                </div>
                <div className="border-l border-white/10 pl-2">
                  <p className="text-2xl sm:text-3xl font-bold text-brand-amber">40%</p>
                  <p className="text-xs text-blue-100 uppercase tracking-wider font-semibold">Hiring Cycle Cut</p>
                </div>
                <div className="border-l border-white/10 pl-2">
                  <p className="text-2xl sm:text-3xl font-bold text-brand-amber">150+</p>
                  <p className="text-xs text-blue-100 uppercase tracking-wider font-semibold">Enterprise Clients</p>
                </div>
                <div className="border-l border-white/10 pl-2">
                  <p className="text-2xl sm:text-3xl font-bold text-brand-amber">100%</p>
                  <p className="text-xs text-blue-100 uppercase tracking-wider font-semibold">Legal &amp; Tax Compliant</p>
                </div>
              </div>
            </div>
          </div>
          {/* Curved section divider at bottom */}
          <div className="curve-divider-bottom" style={{ height: '3vw' }}>
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
              <path d="M0,64L120,80C240,96,480,128,720,128C960,128,1200,96,1320,80L1440,64L1440,120L1320,120C1200,120,960,120,720,120C480,120,240,120,120,120L0,120Z" fill="#fafbfc" />
            </svg>
          </div>
        </section>

        {/* ── 2. Filter & Services Section ── */}
        <section className="py-16 sm:py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-extrabold text-text tracking-tight mb-3">Our Scope of Capabilities</h2>
            <p className="text-text-muted text-base max-w-xl mx-auto">
              Filter through our 16 core business and consulting domains to find the exact support model your business needs.
            </p>
          </div>

          {/* Interactive tabs */}
          <div className="flex flex-wrap justify-center gap-2 mb-12">
            {[
              { id: 'all', label: 'All Services' },
              { id: 'talent', label: 'Talent & Sourcing' },
              { id: 'advisory', label: 'Consulting & Policy' },
              { id: 'technology', label: 'Automation & tech' },
              { id: 'operations', label: 'Operations & Payroll' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-2.5 rounded-full text-xs sm:text-sm font-semibold transition-all duration-200 ${
                  activeTab === tab.id
                    ? 'bg-brand-blue text-white shadow-md'
                    : 'bg-white text-text-muted border border-border hover:bg-surface-muted hover:text-brand-blue'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Grid of services */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {filteredServices.map((service) => {
              const IconComponent = service.icon
              return (
                <article
                  key={service.id}
                  className="premium-card group bg-white rounded-xl border border-border p-8 premium-shadow flex flex-col"
                >
                  {/* Icon */}
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-brand-blue-light text-brand-blue mb-5 group-hover:bg-brand-blue group-hover:text-white group-hover:scale-110 transition-all duration-300">
                    <IconComponent size={24} strokeWidth={2} />
                  </div>

                  {/* Title */}
                  <h3 className="text-lg font-bold text-text mb-3 leading-snug group-hover:text-brand-blue transition-colors">
                    {service.name}
                  </h3>

                  {/* Description */}
                  <p className="text-text-muted text-sm leading-relaxed mb-6 flex-grow">
                    {service.description}
                  </p>

                  {/* Key points/features */}
                  <div className="border-t border-border pt-4">
                    <p className="text-xs uppercase tracking-wider font-bold text-text-muted mb-2">Scope highlights</p>
                    <ul className="space-y-1.5">
                      {service.features.map((f, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs text-text">
                          <CheckCircle2 size={13} className="text-brand-amber mt-0.5 flex-shrink-0" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </article>
              )
            })}
          </div>
        </section>

        {/* ── 3. Our Professional Workflow Section ── */}
        <section className="bg-white py-16 sm:py-20 border-y border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">Our Execution Roadmap</p>
              <h2 className="text-3xl font-extrabold text-text tracking-tight">Structured Strategy, Seamless Delivery</h2>
              <p className="text-text-muted text-sm max-w-lg mx-auto mt-2">
                We believe in rigorous diagnostics, careful system deployment, and sustained tracking to scale organizations.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-8 relative">
              {[
                {
                  step: '01',
                  title: 'Consult & Diagnose',
                  desc: 'Comprehensive diagnostic audits of current policies, team competency matrices, and automation tools.',
                },
                {
                  step: '02',
                  title: 'Design & Strategize',
                  desc: 'Formulating tailored Employee Handbooks, selecting correct ATS systems, and mapping payroll protocols.',
                },
                {
                  step: '03',
                  title: 'Deploy & Integrate',
                  desc: 'Launching customized attendance tracking, leave self-services, digital portals, and contract staffing.',
                },
                {
                  step: '04',
                  title: 'Optimize & Scale',
                  desc: 'Conducting continuous upskilling workshops, evaluating KPI targets, and monitoring workforce analytics.',
                },
              ].map((item, idx) => (
                <div key={idx} className="relative bg-surface-muted p-6 rounded-lg border border-border">
                  <div className="absolute -top-5 left-6 bg-brand-blue text-white w-10 h-10 rounded-full flex items-center justify-center font-black text-sm shadow">
                    {item.step}
                  </div>
                  <h3 className="text-base font-bold text-text mt-4 mb-2">{item.title}</h3>
                  <p className="text-text-muted text-xs leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── 4. Frequently Asked Questions ── */}
        <section className="py-16 sm:py-20 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-extrabold text-text tracking-tight mb-3">Service Inquiries &amp; FAQs</h2>
            <p className="text-text-muted text-sm">
              Answers to critical questions regarding our technology platforms, consulting setups, and outsourcing processes.
            </p>
          </div>

          <div className="space-y-4">
            {FAQS.map((faq, index) => {
              const isOpen = expandedFaq === index
              return (
                <div
                  key={index}
                  className="bg-white rounded-lg border border-border overflow-hidden transition-all duration-300"
                >
                  <button
                    onClick={() => setExpandedFaq(isOpen ? null : index)}
                    className="w-full flex items-center justify-between p-5 text-left font-bold text-text text-sm sm:text-base hover:text-brand-blue transition-colors focus:outline-none"
                  >
                    <span>{faq.question}</span>
                    <ChevronDown
                      size={18}
                      className={`text-text-muted transition-transform duration-300 ${isOpen ? 'rotate-180 text-brand-blue' : ''}`}
                    />
                  </button>
                  {isOpen && (
                    <div className="px-5 pb-5 pt-1 text-sm text-text-muted border-t border-border/40 leading-relaxed bg-[#fcfdfe]">
                      {faq.answer}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>

        {/* ── 5. High-Converting Bottom CTA Banner ── */}
        <section className="relative overflow-hidden bg-brand-blue text-white py-16 sm:py-20">
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue to-brand-blue-dark opacity-90" />
          <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h2 className="text-3xl sm:text-4xl font-extrabold mb-4">Ready to Transform Your Organization?</h2>
            <p className="text-base text-blue-100 max-w-xl mx-auto mb-8 leading-relaxed">
              Book a complimentary strategy consultation with our human capital experts. We will diagnostic your systems and layout a customized roadmap.
            </p>
            <div className="flex flex-col sm:flex-row justify-center items-center gap-4">
              <Button
                onClick={openModal}
                className="w-full sm:w-auto px-8 py-4 font-bold text-sm bg-brand-amber hover:bg-brand-amber-dark text-white border-0 transition-all rounded shadow-md hover:scale-[1.02]"
              >
                Book Free Consultation
              </Button>
              <Button
                onClick={openModal}
                variant="outline"
                className="w-full sm:w-auto px-8 py-4 font-bold text-sm text-white border-white/40 hover:bg-white/10 transition-all rounded"
              >
                Contact HR Expert
              </Button>
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
