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

interface AuthStore {
  user: User | null
  session: Session | null
  loading: boolean
  devMode: boolean
  signInWithEmail: (email: string, password: string) => Promise<void>
  signInWithGoogle: () => Promise<void>
  signInWithGithub: () => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  session: null,
  loading: true,
  devMode: DEV_MODE,

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
      set({ user: DEV_USER, session: null, loading: false })
      return
    }

    try {
      const { data: { session } } = await supabase!.auth.getSession()
      set({
        user: session?.user ?? null,
        session,
        loading: false,
      })

      // Listen for auth changes
      supabase!.auth.onAuthStateChange((_event, session) => {
        set({
          user: session?.user ?? null,
          session,
        })
      })
    } catch (error) {
      console.error('Auth init error:', error)
      set({ loading: false })
    }
  },
}))

// Initialize on load
useAuthStore.getState().initialize()
