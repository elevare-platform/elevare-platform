// HomePage — assembles all home section components in order.
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import HeroSection from '@/components/home/HeroSection'
import SocialProofBar from '@/components/home/SocialProofBar'
import StatsSection from '@/components/home/StatsSection'
import WhyChooseUs from '@/components/home/WhyChooseUs'
import HowItWorks from '@/components/home/HowItWorks'
import Testimonials from '@/components/home/Testimonials'
import JobBoardPreview from '@/components/home/JobBoardPreview'
import FinalCTA from '@/components/home/FinalCTA'

export default function HomePage() {
  return (
    <>
      <Navbar />
      <main>
        <HeroSection />
        <SocialProofBar />
        <StatsSection />
        <WhyChooseUs />
        <HowItWorks />
        <Testimonials />
        <JobBoardPreview />
        <FinalCTA />
      </main>
      <Footer />
    </>
  )
}
