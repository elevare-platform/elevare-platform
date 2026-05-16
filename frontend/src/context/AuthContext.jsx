import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api, { setAccessToken, clearAccessToken } from '@/lib/api'
import { ACCOUNT_STATUS_CODES } from '@/lib/accountStatus'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const { data: refreshData } = await api.post('/api/v1/auth/refresh')
        setAccessToken(refreshData.access_token)
        // /me must work for any account status (requires backend fix on that endpoint).
        // If it returns a 403 with an account-status code, the user is still
        // authenticated — we fall into the catch and handle it there.
        const me = await api.get('/api/v1/auth/me')
        setUser(me.data)
      } catch (err) {
        const code = err.response?.data?.code
        if (ACCOUNT_STATUS_CODES.includes(code)) {
          // Session is valid but account is restricted. Decode the minimal
          // identity from the error response context if available, otherwise
          // the user will see the login page until the backend /me fix is applied.
          // Once the backend returns user data on /me regardless of status,
          // this branch becomes unreachable.
          clearAccessToken()
          setUser(null)
        } else {
          clearAccessToken()
          setUser(null)
        }
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

  const updateUser = useCallback((patch) => {
    setUser((prev) => prev ? { ...prev, ...patch } : prev)
  }, [])

  return (
    <AuthContext.Provider value={{ user, authReady, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

// Returns true if the user is authenticated but their account is restricted
export function isAccountRestricted(user) {
  if (!user) return false
  return user.account_status === 'PENDING_VERIFICATION'
    || user.account_status === 'SUSPENDED'
    || user.account_status === 'BANNED'
    || user.account_status === 'DEACTIVATED'
}

// Derive redirect path after login/register based on user role and profile state
export function getPostAuthRedirect(user) {
  if (!user) return '/login'
  if (user.role === 'EMPLOYER') {
    return user.is_profile_complete ? '/employer/jobs' : '/employer/onboarding'
  }
  return '/dashboard'
}
