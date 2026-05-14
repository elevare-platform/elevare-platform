import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api, { setAccessToken, clearAccessToken } from '@/lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)

  // Bootstrap: on every page load, attempt a silent refresh using the httpOnly cookie.
  // This restores the session without the user having to log in again.
  useEffect(() => {
    const bootstrap = async () => {
      try {
        const { data } = await api.post('/api/v1/auth/refresh')
        setAccessToken(data.access_token)
        // Fetch the user profile with the new token
        const me = await api.get('/api/v1/auth/me')
        setUser(me.data)
      } catch {
        // No valid refresh token — user is not authenticated, that's fine
        clearAccessToken()
        setUser(null)
      } finally {
        setAuthReady(true)
      }
    }
    bootstrap()
  }, [])

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/api/v1/auth/login', { email, password })
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (payload) => {
    const { data } = await api.post('/api/v1/auth/register', payload)
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/api/v1/auth/logout')
    } finally {
      clearAccessToken()
      setUser(null)
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, authReady, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
