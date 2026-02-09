import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authService } from '../services/auth.service'

interface AuthContextValue {
  isAuthenticated: boolean
  authEnabled: boolean
  isLoading: boolean
  login: (password: string) => Promise<boolean>
  logout: () => Promise<void>
  refreshSession: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authEnabled, setAuthEnabled] = useState(true)
  const [isLoading, setIsLoading] = useState(true)

  const refreshSession = useCallback(async () => {
    try {
      const session = await authService.getSession()
      setIsAuthenticated(session.authenticated)
      setAuthEnabled(session.auth_enabled)
    } catch {
      setIsAuthenticated(false)
      setAuthEnabled(true)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshSession()
  }, [refreshSession])

  const login = useCallback(async (password: string): Promise<boolean> => {
    const session = await authService.login(password)
    setIsAuthenticated(session.authenticated)
    setAuthEnabled(session.auth_enabled)
    return session.authenticated
  }, [])

  const logout = useCallback(async () => {
    try {
      const session = await authService.logout()
      setIsAuthenticated(session.authenticated)
      setAuthEnabled(session.auth_enabled)
    } finally {
      setIsAuthenticated(false)
    }
  }, [])

  const value = useMemo(
    () => ({
      isAuthenticated,
      authEnabled,
      isLoading,
      login,
      logout,
      refreshSession,
    }),
    [authEnabled, isAuthenticated, isLoading, login, logout, refreshSession],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
