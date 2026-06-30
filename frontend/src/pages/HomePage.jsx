// HomePage — assembles all home section components in order.
import { useState } from 'react'
import { Helmet } from 'react-helmet-async'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import HeroSection from '@/components/home/HeroSection'
import SocialProofBar from '@/components/home/SocialProofBar'
import PartnersSection from '@/components/home/PartnersSection'
import JobBoardPreview from '@/components/home/JobBoardPreview'
import StorySlider from '@/components/home/StorySlider'
import EmployerJourney from '@/components/home/EmployerJourney'
import ImpactMetrics from '@/components/home/ImpactMetrics'
import ServicesSection from '@/components/home/ServicesSection'
import WhyChooseUs from '@/components/home/WhyChooseUs'
import EmployerStrip from '@/components/home/EmployerStrip'
import CandidateSuccess from '@/components/home/CandidateSuccess'
import HowItWorks from '@/components/home/HowItWorks'
import RecruitmentExcellence from '@/components/home/RecruitmentExcellence'
import Testimonials from '@/components/home/Testimonials'
import InsightsStrip from '@/components/home/InsightsStrip'
import FinalCTA from '@/components/home/FinalCTA'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'

export default function HomePage() {
  const [isModalOpen, setIsModalOpen] = useState(false)

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  return (
    <>
      <Helmet>
        <title>Elevare Human Solutions — Connecting Talent with Opportunity in Africa</title>
        <meta name="description" content="Elevare connects exceptional talent with ambitious companies across Africa. Post a job or find your next role today." />
        <meta property="og:title" content="Elevare Human Solutions — Connecting Talent with Opportunity" />
        <meta property="og:description" content="Elevare connects exceptional talent with ambitious companies across Africa." />
        <meta property="og:url" content="https://elevare.com.ng/" />
        <meta property="og:type" content="website" />
        <link rel="canonical" href="https://elevare.com.ng/" />
      </Helmet>
      <Navbar onBookConsultation={openModal} />
      <main>
        {/* Requirements 1.1–1.5 */}
        <HeroSection onBookConsultation={openModal} />
        
        {/* Credibility & Activity Sections moved immediately after Hero area */}
        <SocialProofBar />
        <PartnersSection />
        <JobBoardPreview />
        
        {/* SECTION TYPE A — Background Image Story Slider */}
        <StorySlider />

        {/* SECTION TYPE B — Employer Journey Showcase */}
        <EmployerJourney />

        {/* SECTION TYPE D — Impact Metrics Section (Replaces old static StatsSection) */}
        <ImpactMetrics />

        {/* Requirements 3.1, 3.2 */}
        <ServicesSection />
        
        <WhyChooseUs />
        
        {/* Requirements 4.1–4.4 */}
        <EmployerStrip onBookConsultation={openModal} />

        {/* SECTION TYPE C — Candidate Success Showcase */}
        <CandidateSuccess />
        
        <HowItWorks />

        {/* SECTION TYPE E — Recruitment Excellence Banner */}
        <RecruitmentExcellence onBookConsultation={openModal} />
        
        <Testimonials />
        
        {/* Requirements 10.1–10.4 */}
        <InsightsStrip />
        
        <FinalCTA />
      </main>
      <Footer onBookConsultation={openModal} />
      <ConsultationModal isOpen={isModalOpen} onClose={closeModal} />
      <FloatingWhatsApp />
    </>
  )
}
