import { create } from 'zustand'
import { supabase } from './auth'

// Dev mode check
const DEV_MODE = !import.meta.env.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL === ''

interface UsageData {
  id: string
  user_id: string
  period_start: string
  period_end: string
  tokens_used: number
  tokens_limit: number
  requests_count: number
  requests_limit: number
  chat_messages: number
  analyses_run: number
  tickets_created: number
  agents_spawned: number
  cost_cents: number
}

interface DailyUsage {
  date: string
  messages: number
  tokens: number
}

interface UsageStore {
  usage: UsageData | null
  dailyUsage: DailyUsage[]
  loading: boolean
  error: string | null
  fetchUsage: () => Promise<void>
  incrementTokens: (count: number) => Promise<void>
  incrementMessages: () => Promise<void>
}

// Mock data for dev mode
const MOCK_USAGE: UsageData = {
  id: 'mock-usage-1',
  user_id: 'dev-user-123',
  period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString(),
  period_end: new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).toISOString(),
  tokens_used: 125000,
  tokens_limit: 500000,
  requests_count: 847,
  requests_limit: 5000,
  chat_messages: 423,
  analyses_run: 12,
  tickets_created: 8,
  agents_spawned: 3,
  cost_cents: 250,
}

const MOCK_DAILY_USAGE: DailyUsage[] = [
  { date: '2024-12-22', messages: 45, tokens: 67500 },
  { date: '2024-12-23', messages: 78, tokens: 117000 },
  { date: '2024-12-24', messages: 123, tokens: 184500 },
  { date: '2024-12-25', messages: 89, tokens: 133500 },
  { date: '2024-12-26', messages: 156, tokens: 234000 },
  { date: '2024-12-27', messages: 201, tokens: 301500 },
  { date: '2024-12-28', messages: 155, tokens: 232500 },
]

export const useUsageStore = create<UsageStore>((set, get) => ({
  usage: null,
  dailyUsage: [],
  loading: false,
  error: null,

  fetchUsage: async () => {
    if (DEV_MODE) {
      console.log('🔧 Dev Mode: Using mock usage data')
      set({ usage: MOCK_USAGE, dailyUsage: MOCK_DAILY_USAGE, loading: false })
      return
    }

    set({ loading: true, error: null })

    try {
      const { data: { user } } = await supabase!.auth.getUser()
      if (!user) {
        set({ loading: false, error: 'Not authenticated' })
        return
      }

      // Get or create current period usage
      const { data, error } = await supabase!
        .rpc('get_current_usage', { p_user_id: user.id })

      if (error) throw error

      set({ usage: data, loading: false })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to fetch usage:', err)
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch usage',
        loading: false
      })
    }
  },

  incrementTokens: async (count: number) => {
    if (DEV_MODE) {
      const currentUsage = get().usage
      if (currentUsage) {
        set({
          usage: {
            ...currentUsage,
            tokens_used: currentUsage.tokens_used + count
          }
        })
      }
      return
    }

    const { usage } = get()
    if (!usage) return

    try {
      const { error } = await supabase!
        .from('usage')
        .update({ tokens_used: usage.tokens_used + count })
        .eq('id', usage.id)

      if (error) throw error

      set({ usage: { ...usage, tokens_used: usage.tokens_used + count } })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to increment tokens:', err)
    }
  },

  incrementMessages: async () => {
    if (DEV_MODE) {
      const currentUsage = get().usage
      if (currentUsage) {
        set({
          usage: {
            ...currentUsage,
            chat_messages: currentUsage.chat_messages + 1,
            requests_count: currentUsage.requests_count + 1,
          }
        })
      }
      return
    }

    const { usage } = get()
    if (!usage) return

    try {
      const { error } = await supabase!
        .from('usage')
        .update({
          chat_messages: usage.chat_messages + 1,
          requests_count: usage.requests_count + 1,
        })
        .eq('id', usage.id)

      if (error) throw error

      set({
        usage: {
          ...usage,
          chat_messages: usage.chat_messages + 1,
          requests_count: usage.requests_count + 1,
        }
      })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to increment messages:', err)
    }
  },
}))
