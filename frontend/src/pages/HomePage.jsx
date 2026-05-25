// HomePage — assembles all home section components in order.
import { useState } from 'react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import HeroSection from '@/components/home/HeroSection'
import SocialProofBar from '@/components/home/SocialProofBar'
import StatsSection from '@/components/home/StatsSection'
import ServicesSection from '@/components/home/ServicesSection'
import WhyChooseUs from '@/components/home/WhyChooseUs'
import EmployerStrip from '@/components/home/EmployerStrip'
import HowItWorks from '@/components/home/HowItWorks'
import Testimonials from '@/components/home/Testimonials'
import JobBoardPreview from '@/components/home/JobBoardPreview'
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
      <Navbar onBookConsultation={openModal} />
      <main>
        {/* Requirements 1.1–1.5 */}
        <HeroSection onBookConsultation={openModal} />
        <SocialProofBar />
        <StatsSection />
        {/* Requirements 3.1, 3.2 */}
        <ServicesSection />
        <WhyChooseUs />
        {/* Requirements 4.1–4.4 */}
        <EmployerStrip onBookConsultation={openModal} />
        <HowItWorks />
        <Testimonials />
        <JobBoardPreview />
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
