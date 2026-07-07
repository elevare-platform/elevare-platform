import { useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { CheckCircle2, AlertCircle, Upload, X } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import api from '@/lib/api'

export default function TestimonialSubmitPage() {
  const [form, setForm] = useState({
    full_name: '',
    company: '',
    position: '',
    testimony: '',
  })
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [status, setStatus] = useState('idle') // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('')

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((f) => ({ ...f, [name]: value }))
  }

  const handleImageChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate type and size
    const validTypes = ['image/jpeg', 'image/png', 'image/webp']
    if (!validTypes.includes(file.type)) {
      setErrorMsg('Image must be JPEG, PNG, or WebP')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setErrorMsg('Image must be under 5 MB')
      return
    }

    setImage(file)
    setImagePreview(URL.createObjectURL(file))
    setErrorMsg('')
  }

  const clearImage = () => {
    setImage(null)
    setImagePreview(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus('loading')
    setErrorMsg('')

    const formData = new FormData()
    formData.append('full_name', form.full_name.trim())
    formData.append('testimony', form.testimony.trim())
    if (form.company.trim()) formData.append('company', form.company.trim())
    if (form.position.trim()) formData.append('position', form.position.trim())
    if (image) formData.append('image', image)

    try {
      await api.post('/api/v1/testimonials', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setStatus('success')
    } catch (err) {
      const data = err.response?.data
      if (typeof data?.detail === 'string') {
        setErrorMsg(data.detail)
      } else {
        setErrorMsg('Something went wrong. Please try again.')
      }
      setStatus('error')
    }
  }

  return (
    <>
      <Helmet>
        <title>Share Your Experience | Elevare Human Solutions</title>
        <meta name="description" content="Help us grow by sharing your experience working with Elevare." />
      </Helmet>
      <Navbar />

      <main className="pt-16 bg-[#fafbfc]">
        {/* Hero */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ backgroundImage: "url('/hero-images/img20.jpg')" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                Testimonial
              </span>
              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight" style={{ fontFamily: "'Lobster Two', cursive" }}>
                Share Your Experience
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-xl">
                Your feedback helps us improve and helps others make informed decisions.
              </p>
            </div>
          </div>
          <div className="curve-divider-bottom" style={{ height: '3vw' }}>
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
              <path d="M0,64L120,80C240,96,480,128,720,128C960,128,1200,96,1320,80L1440,64L1440,120L1320,120C1200,120,960,120,720,120C480,120,240,120,120,120L0,120Z" fill="#fafbfc" />
            </svg>
          </div>
        </section>

        {/* Form */}
        <section className="py-16 sm:py-24 max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          {status === 'success' ? (
            <div className="flex flex-col items-center justify-center text-center py-16 gap-4">
              <CheckCircle2 size={48} className="text-green-500" />
              <h2 className="text-2xl font-extrabold text-text">Thank You!</h2>
              <p className="text-text-muted text-sm max-w-sm">
                Your testimonial has been submitted. We'll review it and publish it shortly.
              </p>
              <button
                className="mt-4 text-sm text-brand-blue font-semibold hover:underline"
                onClick={() => {
                  setStatus('idle')
                  setForm({ full_name: '', company: '', position: '', testimony: '' })
                  clearImage()
                }}
              >
                Submit another
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate className="space-y-5">
              <h2 className="text-2xl font-extrabold text-text mb-6">Your Testimonial</h2>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="full_name" className="text-xs font-bold text-text uppercase tracking-wider">
                  Full Name <span className="text-red-500">*</span>
                </label>
                <input
                  id="full_name"
                  name="full_name"
                  type="text"
                  required
                  value={form.full_name}
                  onChange={handleChange}
                  placeholder="Jane Doe"
                  className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="company" className="text-xs font-bold text-text uppercase tracking-wider">
                    Company <span className="text-text-muted font-normal normal-case">(optional)</span>
                  </label>
                  <input
                    id="company"
                    name="company"
                    type="text"
                    value={form.company}
                    onChange={handleChange}
                    placeholder="Acme Ltd"
                    className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="position" className="text-xs font-bold text-text uppercase tracking-wider">
                    Position <span className="text-text-muted font-normal normal-case">(optional)</span>
                  </label>
                  <input
                    id="position"
                    name="position"
                    type="text"
                    value={form.position}
                    onChange={handleChange}
                    placeholder="CEO"
                    className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="testimony" className="text-xs font-bold text-text uppercase tracking-wider">
                  Your Testimonial <span className="text-red-500">*</span>
                </label>
                <textarea
                  id="testimony"
                  name="testimony"
                  required
                  rows={6}
                  value={form.testimony}
                  onChange={handleChange}
                  placeholder="Share your experience working with Elevare..."
                  className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue resize-none"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="image" className="text-xs font-bold text-text uppercase tracking-wider">
                  Your Photo <span className="text-text-muted font-normal normal-case">(optional, max 5 MB)</span>
                </label>
                {imagePreview ? (
                  <div className="relative inline-block">
                    <img
                      src={imagePreview}
                      alt="Preview"
                      className="w-24 h-24 rounded-full object-cover border-2 border-border"
                    />
                    <button
                      type="button"
                      onClick={clearImage}
                      className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ) : (
                  <label
                    htmlFor="image"
                    className="flex items-center justify-center gap-2 w-full rounded-lg border-2 border-dashed border-border px-4 py-8 cursor-pointer hover:border-brand-blue transition-colors"
                  >
                    <Upload size={18} className="text-text-muted" />
                    <span className="text-sm text-text-muted">Click to upload (JPEG, PNG, WebP)</span>
                    <input
                      id="image"
                      name="image"
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleImageChange}
                      className="hidden"
                    />
                  </label>
                )}
              </div>

              {status === 'error' && (
                <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3" role="alert">
                  <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{errorMsg}</p>
                </div>
              )}

              <Button
                type="submit"
                disabled={status === 'loading'}
                className="w-full sm:w-auto bg-brand-blue hover:bg-brand-blue/90 text-white border-0 px-10 py-3 text-sm font-bold uppercase tracking-wider rounded-full"
              >
                {status === 'loading' ? 'Submitting…' : 'Submit Testimonial'}
              </Button>
            </form>
          )}
        </section>
      </main>

      <Footer />
      <FloatingWhatsApp />
    </>
  )
}
