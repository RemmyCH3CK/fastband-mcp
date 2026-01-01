import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import { useCallback, useState, lazy, Suspense } from 'react'
// Core pages - loaded immediately
import { Chat } from './pages/Chat'
import { ControlPlane } from './pages/ControlPlane'
import { Login } from './pages/Login'
import { Onboarding } from './pages/Onboarding'
// Lazy-loaded pages for code splitting
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })))
const Backups = lazy(() => import('./pages/Backups').then(m => ({ default: m.Backups })))
const Analyze = lazy(() => import('./pages/Analyze').then(m => ({ default: m.Analyze })))
const Tickets = lazy(() => import('./pages/Tickets').then(m => ({ default: m.Tickets })))
const Usage = lazy(() => import('./pages/Usage').then(m => ({ default: m.Usage })))
const BibleEditor = lazy(() => import('./pages/BibleEditor').then(m => ({ default: m.BibleEditor })))
import { Layout } from './components/Layout'
import { ToastContainer } from './components/Toast'
import { OnboardingModal } from './components/onboarding/OnboardingModal'
import { toast } from './stores/toast'

// Loading fallback for lazy-loaded routes
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-void-900">
      <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan" />
    </div>
  )
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, onboardingCompleted, completeOnboarding } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [isRestarting, setIsRestarting] = useState(false)

  const handleOnboardingComplete = useCallback(async (data: Parameters<typeof completeOnboarding>[0]) => {
    // Complete onboarding - this also reinitializes chat manager with new API keys
    setIsRestarting(true)
    toast.info('Applying Configuration', 'Setting up your environment...')

    try {
      // Call completeOnboarding which saves data and reinitializes chat
      const response = await fetch('/api/onboarding/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (response.ok) {
        const result = await response.json()

        // Update local state
        completeOnboarding(data)

        if (result.chatReady) {
          toast.success('Configuration Applied', 'You\'re all set! Chat is ready.')
        } else {
          // Chat couldn't be initialized - may need manual restart
          toast.warning('Partial Setup', 'Configuration saved. You may need to restart the server for chat.')
        }
      } else {
        toast.error('Setup Error', 'Failed to save configuration. Please try again.')
      }
    } catch (error) {
      if (import.meta.env.DEV) {
        console.warn('Onboarding complete failed:', error)
      }
      // Still mark as complete locally so user can proceed
      completeOnboarding(data)
      toast.warning('Offline Mode', 'Configuration saved locally. Server sync may be needed.')
    } finally {
      setIsRestarting(false)
    }

    // Navigate to Control Plane after onboarding
    if (location.pathname !== '/') {
      navigate('/', { replace: true })
    }
  }, [completeOnboarding, navigate, location.pathname])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  // Show restart indicator
  if (isRestarting) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-void-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-cyan mb-4" />
        <p className="text-cyan font-medium">Applying configuration...</p>
        <p className="text-slate-500 text-sm mt-2">Server is restarting with your new settings</p>
      </div>
    )
  }

  // Show onboarding modal for first-time users
  if (!onboardingCompleted) {
    return (
      <OnboardingModal
        isOpen={true}
        onComplete={handleOnboardingComplete}
        initialProjectPath=""
      />
    )
  }

  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/onboarding" element={<Onboarding />} />
        {/* Control Plane is the home page */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout showConversationSidebar={false}>
                <ControlPlane />
              </Layout>
            </ProtectedRoute>
          }
        />
        {/* Chat page */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Layout>
                <Chat />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/analyze"
          element={
            <ProtectedRoute>
              <Suspense fallback={<PageLoader />}>
                <Analyze />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/usage"
          element={
            <ProtectedRoute>
              <Suspense fallback={<PageLoader />}>
                <Usage />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Suspense fallback={<PageLoader />}>
                <Settings />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/backups"
          element={
            <ProtectedRoute>
              <Suspense fallback={<PageLoader />}>
                <Backups />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets"
          element={
            <ProtectedRoute>
              <Suspense fallback={<PageLoader />}>
                <Tickets />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/conversation/:id"
          element={
            <ProtectedRoute>
              <Layout>
                <Chat />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/bible"
          element={
            <ProtectedRoute>
              <Suspense fallback={<PageLoader />}>
                <BibleEditor />
              </Suspense>
            </ProtectedRoute>
          }
        />
      </Routes>
    </QueryClientProvider>
  )
}
