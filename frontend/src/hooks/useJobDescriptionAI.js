import { useCallback, useState } from 'react'
import { generateJobDescriptionText } from '@/services/aiJobDescription'

/**
 * Drives a single AI-assist request/response cycle for one job description field.
 * Follows the loading/error/data pattern used by other data hooks in this app.
 */
export function useJobDescriptionAI() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [suggestion, setSuggestion] = useState(null)

  const generate = useCallback(async ({ mode, field, currentText, jobContext }) => {
    setLoading(true)
    setError(null)
    try {
      const { text } = await generateJobDescriptionText({ mode, field, currentText, jobContext })
      setSuggestion(text)
      return text
    } catch (err) {
      setError(err?.response?.data?.detail || 'Something went wrong generating a suggestion. Please try again.')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setSuggestion(null)
    setError(null)
  }, [])

  return { loading, error, suggestion, generate, reset }
}
