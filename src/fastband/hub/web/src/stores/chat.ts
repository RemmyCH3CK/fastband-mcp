import { create } from 'zustand'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  toolCalls?: Array<{
    toolId: string
    toolName: string
    result?: unknown
  }>
  createdAt: Date
}

interface ChatStore {
  messages: Message[]
  addMessage: (message: Message) => void
  updateLastMessage: (content: string) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages]
      if (messages.length > 0) {
        messages[messages.length - 1] = {
          ...messages[messages.length - 1],
          content,
        }
      }
      return { messages }
    }),

  clearMessages: () => set({ messages: [] }),
}))
