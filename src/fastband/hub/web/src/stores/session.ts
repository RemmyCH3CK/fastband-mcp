import { create } from 'zustand'

interface SessionStore {
  sessionId: string | null
  conversationId: string | null
  tier: 'free' | 'pro' | 'enterprise'
  createSession: (userId: string) => Promise<void>
  setConversation: (id: string) => void
  clearSession: () => void
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  sessionId: null,
  conversationId: null,
  tier: 'free',

  createSession: async (userId: string) => {
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
      sessionId: null,
      conversationId: null,
      tier: 'free',
    }),
}))
