import { FormEvent, useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { login, isAuthenticated, authEnabled, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const redirectPath =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/'

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(redirectPath, { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate, redirectPath])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      const ok = await login(password)
      if (!ok) {
        toast.error('Invalid password')
        return
      }
      navigate(redirectPath, { replace: true })
    } catch {
      toast.error('Login failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isLoading && !authEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0f0f1a] via-[#1a1a2e] to-[#0f0f1a] px-4">
        <div className="w-full max-w-md bg-black/30 border border-gray-800 rounded-2xl p-8 text-center">
          <p className="text-gray-200">Server authentication is disabled.</p>
          <button
            type="button"
            onClick={() => navigate('/', { replace: true })}
            className="mt-6 w-full py-3 rounded-xl bg-math-blue hover:bg-blue-600 transition-colors font-semibold"
          >
            Continue
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0f0f1a] via-[#1a1a2e] to-[#0f0f1a] px-4">
      <div className="w-full max-w-md bg-black/30 border border-gray-800 rounded-2xl p-8 shadow-2xl">
        <div className="flex items-center justify-center mb-6">
          <div className="p-3 rounded-full bg-math-blue/20">
            <Lock className="w-6 h-6 text-math-blue" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-center text-white mb-2">Sign in</h1>
        <p className="text-center text-gray-400 mb-8">Enter password to access EduViz</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-sm text-gray-300 mb-2">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-3 bg-gray-900/70 border border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-math-blue text-white"
              placeholder="Enter password"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 rounded-xl bg-math-blue hover:bg-blue-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors font-semibold"
          >
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
