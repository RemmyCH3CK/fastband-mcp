import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import { useCallback } from 'react'
import { Backups } from './pages/Backups'
import { Chat } from './pages/Chat'
import { ControlPlane } from './pages/ControlPlane'
import { Login } from './pages/Login'
import { Onboarding } from './pages/Onboarding'
import { Settings } from './pages/Settings'
import { Analyze } from './pages/Analyze'
import { Tickets } from './pages/Tickets'
import { Usage } from './pages/Usage'
import { BibleEditor } from './pages/BibleEditor'
import { Layout } from './components/Layout'
import { ToastContainer } from './components/Toast'
import { OnboardingModal } from './components/onboarding/OnboardingModal'

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

  const handleOnboardingComplete = useCallback((data: Parameters<typeof completeOnboarding>[0]) => {
    completeOnboarding(data)
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
              <Analyze />
            </ProtectedRoute>
          }
        />
        <Route
          path="/usage"
          element={
            <ProtectedRoute>
              <Usage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/backups"
          element={
            <ProtectedRoute>
              <Backups />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets"
          element={
            <ProtectedRoute>
              <Tickets />
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
              <BibleEditor />
            </ProtectedRoute>
          }
        />
      </Routes>
    </QueryClientProvider>
  )
}
