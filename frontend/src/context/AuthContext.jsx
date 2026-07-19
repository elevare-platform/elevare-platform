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
        const me = await api.get('/api/v1/auth/me')
        const userData = me.data

        // For employers, /me doesn't include is_profile_complete/kyc_status (they
        // live on employer_profile, not on the User model). Fetch separately so
        // the onboarding/verification redirects work correctly on every page load.
        if (userData.role === 'EMPLOYER') {
          try {
            const { data: profile } = await api.get('/api/v1/employer/profile')
            userData.is_profile_complete = profile.is_profile_complete ?? false
            userData.kyc_status = profile.kyc_status ?? 'NOT_SUBMITTED'
          } catch {
            // If profile fetch fails, default so onboarding/verification is shown
            userData.is_profile_complete = false
            userData.kyc_status = 'NOT_SUBMITTED'
          }
        }

        setUser(userData)
      } catch (err) {
        const code = err.response?.data?.code
        if (ACCOUNT_STATUS_CODES.includes(code)) {
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
    const userData = data.user
    // Populate is_profile_complete/kyc_status for employers (not in login response)
    if (userData.role === 'EMPLOYER') {
      try {
        const { data: profile } = await api.get('/api/v1/employer/profile')
        userData.is_profile_complete = profile.is_profile_complete ?? false
        userData.kyc_status = profile.kyc_status ?? 'NOT_SUBMITTED'
      } catch {
        userData.is_profile_complete = false
        userData.kyc_status = 'NOT_SUBMITTED'
      }
    }
    setUser(userData)
    return userData
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
    if (!user.is_profile_complete) return '/employer/onboarding'
    if (user.kyc_status !== 'APPROVED') return '/employer/verification'
    return '/dashboard'
  }
  if (user.role === 'CANDIDATE') {
    return '/candidate/dashboard'
  }
  if (user.role === 'ADMIN') {
    return '/admin/dashboard'
  }
  return '/dashboard'
}
