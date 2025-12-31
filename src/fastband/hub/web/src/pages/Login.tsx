import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Github, Mail, Loader2, Zap, ArrowRight, Eye, EyeOff } from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '../stores/auth'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const navigate = useNavigate()
  const { signInWithEmail, signInWithGoogle, signInWithGithub, signUp } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      if (isSignUp) {
        await signUp(email, password)
      } else {
        await signInWithEmail(email, password)
      }
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const handleOAuth = async (provider: 'google' | 'github') => {
    setLoading(true)
    setError('')

    try {
      if (provider === 'google') {
        await signInWithGoogle()
      } else {
        await signInWithGithub()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'OAuth failed')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-void-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-grid opacity-50" />
      <div className="absolute inset-0 bg-gradient-radial from-cyan/5 via-transparent to-transparent" />
      <div className="absolute top-1/4 -left-32 w-64 h-64 bg-cyan/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 -right-32 w-64 h-64 bg-magenta/10 rounded-full blur-3xl" />

      {/* Scan line effect */}
      <div className="scan-line absolute inset-0 pointer-events-none opacity-30" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-10 animate-in">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-cyan/20 via-void-800 to-magenta/20 border border-cyan/30 flex items-center justify-center logo-glow animate-float">
            <Zap className="w-10 h-10 text-cyan" />
          </div>
          <h1 className="text-4xl font-display font-bold">
            <span className="text-gradient">Fastband</span>
            <span className="text-slate-100"> Hub</span>
          </h1>
          <p className="text-slate-400 mt-3 font-body">
            Your AI-powered development command center
          </p>
        </div>

        {/* Card */}
        <div className="card-glow p-8 animate-in" style={{ animationDelay: '0.1s' }}>
          <h2 className="text-xl font-display font-semibold text-slate-100 mb-6 flex items-center gap-2">
            {isSignUp ? (
              <>
                <span className="w-2 h-2 rounded-full bg-magenta animate-pulse" />
                Create Account
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-cyan animate-pulse" />
                Welcome Back
              </>
            )}
          </h2>

          {error && (
            <div className="mb-6 p-4 bg-error/10 border border-error/30 rounded-lg text-error text-sm animate-in">
              {error}
            </div>
          )}

          {/* OAuth Buttons */}
          <div className="space-y-3 mb-6">
            <button
              onClick={() => handleOAuth('google')}
              disabled={loading}
              className={clsx(
                'w-full flex items-center justify-center gap-3 px-4 py-3.5 rounded-xl',
                'bg-white text-void-900 font-medium',
                'hover:bg-slate-100 transition-all duration-200',
                'hover:shadow-lg hover:-translate-y-0.5',
                'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none'
              )}
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </button>

            <button
              onClick={() => handleOAuth('github')}
              disabled={loading}
              className={clsx(
                'w-full flex items-center justify-center gap-3 px-4 py-3.5 rounded-xl',
                'bg-void-700 text-slate-100 font-medium border border-void-600',
                'hover:bg-void-600 hover:border-slate-500 transition-all duration-200',
                'hover:shadow-lg hover:-translate-y-0.5',
                'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none'
              )}
            >
              <Github className="w-5 h-5" />
              Continue with GitHub
            </button>
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-void-600" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-void-800 text-slate-500 font-mono text-xs uppercase tracking-wider">
                Or continue with email
              </span>
            </div>
          </div>

          {/* Email Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-2">
                Email address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input-field"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="input-field pr-12"
                  placeholder="Min. 8 characters"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 group"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Mail className="w-5 h-5" />
                  {isSignUp ? 'Create Account' : 'Sign In'}
                  <ArrowRight className="w-4 h-4 opacity-0 -ml-4 group-hover:opacity-100 group-hover:ml-0 transition-all" />
                </>
              )}
            </button>
          </form>

          {/* Toggle sign up/in */}
          <p className="mt-6 text-center text-slate-400">
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              onClick={() => {
                setIsSignUp(!isSignUp)
                setError('')
              }}
              className="text-cyan hover:text-cyan-300 font-medium transition-colors"
            >
              {isSignUp ? 'Sign In' : 'Sign Up'}
            </button>
          </p>
        </div>

        {/* Footer */}
        <p className="text-center text-slate-600 text-sm mt-8 animate-in" style={{ animationDelay: '0.2s' }}>
          By continuing, you agree to our{' '}
          <a href="/terms" className="text-slate-500 hover:text-cyan transition-colors">Terms</a>
          {' '}and{' '}
          <a href="/privacy" className="text-slate-500 hover:text-cyan transition-colors">Privacy Policy</a>
        </p>
      </div>
    </div>
  )
}
