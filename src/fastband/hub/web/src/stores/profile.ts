import { create } from 'zustand'
import { supabase } from './auth'

// Dev mode check
const DEV_MODE = !import.meta.env.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL === ''

interface Profile {
  id: string
  email: string | null
  full_name: string | null
  avatar_url: string | null
  tier: 'free' | 'pro' | 'enterprise'
  created_at: string
  updated_at: string
}

interface ProfileStore {
  profile: Profile | null
  loading: boolean
  error: string | null
  fetchProfile: () => Promise<void>
  updateProfile: (updates: Partial<Profile>) => Promise<void>
}

// Mock profile for dev mode
const MOCK_PROFILE: Profile = {
  id: 'dev-user-123',
  email: 'dev@fastband.local',
  full_name: 'Dev User',
  avatar_url: null,
  tier: 'pro',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

export const useProfileStore = create<ProfileStore>((set, get) => ({
  profile: null,
  loading: false,
  error: null,

  fetchProfile: async () => {
    if (DEV_MODE) {
      console.log('🔧 Dev Mode: Using mock profile')
      set({ profile: MOCK_PROFILE, loading: false })
      return
    }

    set({ loading: true, error: null })

    try {
      const { data: { user } } = await supabase!.auth.getUser()
      if (!user) {
        set({ loading: false, error: 'Not authenticated' })
        return
      }

      const { data, error } = await supabase!
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single()

      if (error) throw error

      set({ profile: data, loading: false })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to fetch profile:', err)
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch profile',
        loading: false
      })
    }
  },

  updateProfile: async (updates: Partial<Profile>) => {
    if (DEV_MODE) {
      const currentProfile = get().profile
      if (currentProfile) {
        set({
          profile: {
            ...currentProfile,
            ...updates,
            updated_at: new Date().toISOString()
          }
        })
      }
      return
    }

    const { profile } = get()
    if (!profile) return

    set({ loading: true, error: null })

    try {
      const { data, error } = await supabase!
        .from('profiles')
        .update(updates)
        .eq('id', profile.id)
        .select()
        .single()

      if (error) throw error

      set({ profile: data, loading: false })
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to update profile:', err)
      set({
        error: err instanceof Error ? err.message : 'Failed to update profile',
        loading: false
      })
    }
  },
}))
