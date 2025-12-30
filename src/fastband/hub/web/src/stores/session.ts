import { create } from 'zustand'

// Dev mode - use mock session
const DEV_MODE = !import.meta.env.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL === ''

interface SessionStore {
  sessionId: string | null
  conversationId: string | null
  tier: 'free' | 'pro' | 'enterprise'
  createSession: (userId: string) => Promise<void>
  setConversation: (id: string) => void
  clearSession: () => void
}

export const useSessionStore = create<SessionStore>((set, _get) => ({
  sessionId: DEV_MODE ? 'dev-session-123' : null,
  conversationId: null,
  tier: 'pro', // Give dev mode pro tier for testing all features

  createSession: async (userId: string) => {
    if (DEV_MODE) {
      // Mock session in dev mode
      console.log('🔧 Dev Mode: Using mock session')
      set({
        sessionId: `dev-session-${Date.now()}`,
        tier: 'pro',
      })
      return
    }

    try {
      const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          tier: 'free',
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to create session')
      }

      const data = await response.json()
      set({
        sessionId: data.session_id,
        tier: data.tier,
      })
    } catch (error) {
      console.error('Session creation error:', error)
      throw error
    }
  },

  setConversation: (id) => set({ conversationId: id }),

  clearSession: () =>
    set({
      sessionId: DEV_MODE ? 'dev-session-123' : null,
      conversationId: null,
      tier: DEV_MODE ? 'pro' : 'free',
    }),
}))
