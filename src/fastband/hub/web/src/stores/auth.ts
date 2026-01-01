import { create } from 'zustand'
import { createClient, User, Session } from '@supabase/supabase-js'

// Dev mode - bypasses Supabase auth for local testing
const DEV_MODE = !import.meta.env.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL === ''

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://placeholder.supabase.co'
const supabaseKey = import.meta.env.VITE_SUPABASE_KEY || 'placeholder-key'

export const supabase = DEV_MODE ? null : createClient(supabaseUrl, supabaseKey)

// Mock user for dev mode
const DEV_USER: User = {
  id: 'dev-user-123',
  email: 'dev@fastband.local',
  app_metadata: {},
  user_metadata: { name: 'Dev User' },
  aud: 'authenticated',
  created_at: new Date().toISOString(),
}

interface OnboardingData {
  projectPath: string
  githubUrl: string
  operationMode: 'manual' | 'yolo'
  backupEnabled: boolean
  ticketsEnabled: boolean
  providers: {
    anthropic: { key: string; valid: boolean }
    openai: { key: string; valid: boolean }
    gemini: { key: string; valid: boolean }
    ollama: { host: string; valid: boolean }
  }
  analysisComplete: boolean
  bibleGenerated: boolean
  techStack: string[]
  selectedTools: string[]
  maxRecommendedTools: number
}

interface AuthStore {
  user: User | null
  session: Session | null
  loading: boolean
  devMode: boolean
  onboardingCompleted: boolean
  onboardingData: OnboardingData | null
  signInWithEmail: (email: string, password: string) => Promise<void>
  signInWithGoogle: () => Promise<void>
  signInWithApple: () => Promise<void>
  signInWithGithub: () => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  initialize: () => Promise<void>
  completeOnboarding: (data: OnboardingData) => void
  resetOnboarding: () => void
}

// Helper to get localStorage key for a user (per-user isolation)
const getOnboardingKey = (userId?: string): string => {
  if (userId) {
    return `fastband_onboarding_${userId}`
  }
  return 'fastband_onboarding'
}

// Helper to get onboarding status from localStorage for a specific user
const getStoredOnboardingStatus = (userId?: string): { completed: boolean; data: OnboardingData | null } => {
  try {
    const key = getOnboardingKey(userId)
    const stored = localStorage.getItem(key)
    if (stored) {
      const parsed = JSON.parse(stored)
      return { completed: true, data: parsed }
    }
  } catch {
    // Ignore parse errors
  }
  return { completed: false, data: null }
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  session: null,
  loading: true,
  devMode: DEV_MODE,
  // Initially false - will be set properly in initialize() after we know the user
  onboardingCompleted: false,
  onboardingData: null,

  signInWithEmail: async (email, password) => {
    if (DEV_MODE) {
      // Dev mode - auto login
      set({ user: { ...DEV_USER, email }, session: null, loading: false })
      return
    }

    const { data, error } = await supabase!.auth.signInWithPassword({
      email,
      password,
    })
    if (error) throw error
    set({ user: data.user, session: data.session })
  },

  signInWithGoogle: async () => {
    if (DEV_MODE) {
      set({ user: DEV_USER, session: null, loading: false })
      return
    }

    const { error } = await supabase!.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin,
      },
    })
    if (error) throw error
  },

  signInWithApple: async () => {
    if (DEV_MODE) {
      set({ user: DEV_USER, session: null, loading: false })
      return
    }

    const { error } = await supabase!.auth.signInWithOAuth({
      provider: 'apple',
      options: {
        redirectTo: window.location.origin,
      },
    })
    if (error) throw error
  },

  signInWithGithub: async () => {
    if (DEV_MODE) {
      set({ user: DEV_USER, session: null, loading: false })
      return
    }

    const { error } = await supabase!.auth.signInWithOAuth({
      provider: 'github',
      options: {
        redirectTo: window.location.origin,
      },
    })
    if (error) throw error
  },

  signUp: async (email, password) => {
    if (DEV_MODE) {
      set({ user: { ...DEV_USER, email }, session: null, loading: false })
      return
    }

    const { data, error } = await supabase!.auth.signUp({
      email,
      password,
    })
    if (error) throw error
    set({ user: data.user, session: data.session })
  },

  signOut: async () => {
    if (DEV_MODE) {
      set({ user: null, session: null })
      return
    }

    const { error } = await supabase!.auth.signOut()
    if (error) throw error
    set({ user: null, session: null })
  },

  initialize: async () => {
    if (DEV_MODE) {
      // Auto-login in dev mode
      console.log('🔧 Dev Mode: Auth bypassed - auto-logged in as dev@fastband.local')
      const devStatus = getStoredOnboardingStatus(DEV_USER.id)
      set({
        user: DEV_USER,
        session: null,
        loading: false,
        onboardingCompleted: devStatus.completed,
        onboardingData: devStatus.data,
      })
      return
    }

    try {
      const { data: { session } } = await supabase!.auth.getSession()
      const userId = session?.user?.id
      const onboardingStatus = getStoredOnboardingStatus(userId)

      set({
        user: session?.user ?? null,
        session,
        loading: false,
        onboardingCompleted: onboardingStatus.completed,
        onboardingData: onboardingStatus.data,
      })

      // Listen for auth changes and update onboarding status per-user
      supabase!.auth.onAuthStateChange((_event, session) => {
        const newUserId = session?.user?.id
        const newOnboardingStatus = getStoredOnboardingStatus(newUserId)

        set({
          user: session?.user ?? null,
          session,
          onboardingCompleted: newOnboardingStatus.completed,
          onboardingData: newOnboardingStatus.data,
        })
      })
    } catch (error) {
      if (import.meta.env.DEV) console.error('Auth init error:', error)
      set({ loading: false })
    }
  },

  completeOnboarding: (data: OnboardingData) => {
    const userId = get().user?.id
    const key = getOnboardingKey(userId)

    // Store in localStorage with user-specific key
    localStorage.setItem(key, JSON.stringify(data))

    // Also send to backend to save configuration
    fetch('/api/onboarding/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).catch(err => {
      if (import.meta.env.DEV) console.warn('Failed to save onboarding to backend:', err)
    })

    set({ onboardingCompleted: true, onboardingData: data })
  },

  resetOnboarding: () => {
    const userId = get().user?.id
    const key = getOnboardingKey(userId)

    localStorage.removeItem(key)
    set({ onboardingCompleted: false, onboardingData: null })
  },
}))

// Initialize on load
useAuthStore.getState().initialize()
