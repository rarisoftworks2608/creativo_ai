import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { fetchProfile, login as loginRequest, logout as logoutRequest } from '../api/auth'
import { getTokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const tokens = getTokens()
    if (!tokens?.access) {
      setLoading(false)
      return
    }
    fetchProfile()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === 'admin',
      async login(email, password) {
        const loggedInUser = await loginRequest(email, password)
        setUser(loggedInUser)
        return loggedInUser
      },
      async logout() {
        await logoutRequest()
        setUser(null)
      },
    }),
    [user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider.')
  return context
}
