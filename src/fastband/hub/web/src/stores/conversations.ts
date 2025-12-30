import { create } from 'zustand'

// Dev mode - use mock data
const DEV_MODE = !import.meta.env.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL === ''

export interface Conversation {
  id: string
  title: string
  createdAt: Date
  updatedAt: Date
  messageCount: number
}

// Mock conversations for dev mode
const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: 'conv-1',
    title: 'Debug Python async issue',
    createdAt: new Date(),
    updatedAt: new Date(),
    messageCount: 5,
  },
  {
    id: 'conv-2',
    title: 'Refactor authentication flow',
    createdAt: new Date(Date.now() - 86400000), // Yesterday
    updatedAt: new Date(Date.now() - 86400000),
    messageCount: 12,
  },
  {
    id: 'conv-3',
    title: 'Add API rate limiting',
    createdAt: new Date(Date.now() - 86400000 * 3), // 3 days ago
    updatedAt: new Date(Date.now() - 86400000 * 3),
    messageCount: 8,
  },
]

interface ConversationsStore {
  conversations: Conversation[]
  activeId: string | null
  isLoading: boolean
  error: string | null

  fetchConversations: () => Promise<void>
  createConversation: (title?: string) => Promise<Conversation>
  setActive: (id: string) => void
  deleteConversation: (id: string) => Promise<void>
  updateTitle: (id: string, title: string) => void
}

export const useConversationsStore = create<ConversationsStore>((set, _get) => ({
  conversations: DEV_MODE ? MOCK_CONVERSATIONS : [],
  activeId: null,
  isLoading: false,
  error: null,

  fetchConversations: async () => {
    if (DEV_MODE) {
      console.log('🔧 Dev Mode: Using mock conversations')
      set({ conversations: MOCK_CONVERSATIONS, isLoading: false })
      return
    }

    set({ isLoading: true, error: null })
    try {
      const response = await fetch('/api/conversations')
      if (!response.ok) throw new Error('Failed to fetch conversations')

      const data = await response.json()
      const conversations = data.conversations.map((c: any) => ({
        id: c.id,
        title: c.title || 'New Chat',
        createdAt: new Date(c.created_at),
        updatedAt: new Date(c.updated_at),
        messageCount: c.message_count || 0,
      }))

      set({ conversations, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  createConversation: async (title = 'New Chat') => {
    if (DEV_MODE) {
      const conversation: Conversation = {
        id: `conv-${Date.now()}`,
        title,
        createdAt: new Date(),
        updatedAt: new Date(),
        messageCount: 0,
      }
      set((state) => ({
        conversations: [conversation, ...state.conversations],
        activeId: conversation.id,
      }))
      return conversation
    }

    try {
      const response = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      })

      if (!response.ok) throw new Error('Failed to create conversation')

      const data = await response.json()
      const conversation: Conversation = {
        id: data.id,
        title: data.title || title,
        createdAt: new Date(data.created_at),
        updatedAt: new Date(data.created_at),
        messageCount: 0,
      }

      set((state) => ({
        conversations: [conversation, ...state.conversations],
        activeId: conversation.id,
      }))

      return conversation
    } catch (error) {
      set({ error: (error as Error).message })
      throw error
    }
  },

  setActive: (id) => {
    set({ activeId: id })
  },

  deleteConversation: async (id) => {
    if (DEV_MODE) {
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== id),
        activeId: state.activeId === id ? null : state.activeId,
      }))
      return
    }

    try {
      const response = await fetch(`/api/conversations/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to delete conversation')

      set((state) => {
        const newConversations = state.conversations.filter((c) => c.id !== id)
        return {
          conversations: newConversations,
          activeId: state.activeId === id ? null : state.activeId,
        }
      })
    } catch (error) {
      set({ error: (error as Error).message })
      throw error
    }
  },

  updateTitle: (id, title) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }))
  },
}))
