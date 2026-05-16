import axios from 'axios'
import { ACCOUNT_STATUS_CODES } from '@/lib/accountStatus'

// In-memory token — never stored in localStorage or cookies
let accessToken = null

export const setAccessToken = (token) => { accessToken = token }
export const getAccessToken = () => accessToken
export const clearAccessToken = () => { accessToken = null }

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true, // sends httpOnly refresh token cookie automatically
  headers: {
    'ngrok-skip-browser-warning': 'true',
  },
})

// Request interceptor — attach Bearer token to every outgoing request
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

// Flag to prevent infinite refresh loops
let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error)
    else prom.resolve(token)
  })
  failedQueue = []
}

// Response interceptor — on 401, silently refresh and retry original request
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't attempt refresh for auth endpoints themselves
      const isAuthEndpoint = originalRequest.url?.includes('/api/v1/auth/')
      if (isAuthEndpoint) {
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Queue requests that come in while a refresh is already in flight
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await api.post('/api/v1/auth/refresh')
        setAccessToken(data.access_token)
        processQueue(null, data.access_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearAccessToken()
        // Don't redirect if the failure is an account-status restriction —
        // the user is still authenticated, just restricted. Let the UI handle it.
        const code = refreshError.response?.data?.code
        if (!ACCOUNT_STATUS_CODES.includes(code)) {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default api
