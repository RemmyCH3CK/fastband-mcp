/**
 * Tests for Toast Store.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { act } from '@testing-library/react'
import { useToastStore, toast } from './toast'

describe('Toast Store', () => {
  beforeEach(() => {
    // Reset store
    useToastStore.setState({ toasts: [] })
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('addToast', () => {
    it('adds a toast to the store', () => {
      act(() => {
        useToastStore.getState().addToast({
          type: 'success',
          title: 'Test Toast',
          message: 'This is a test',
        })
      })

      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].title).toBe('Test Toast')
      expect(toasts[0].message).toBe('This is a test')
      expect(toasts[0].type).toBe('success')
    })

    it('returns toast id', () => {
      let id: string = ''

      act(() => {
        id = useToastStore.getState().addToast({
          type: 'info',
          title: 'Info Toast',
        })
      })

      expect(id).toMatch(/^toast-\d+$/)
    })

    it('auto-removes toast after duration', () => {
      act(() => {
        useToastStore.getState().addToast({
          type: 'success',
          title: 'Auto-dismiss',
          duration: 3000,
        })
      })

      expect(useToastStore.getState().toasts).toHaveLength(1)

      act(() => {
        vi.advanceTimersByTime(3000)
      })

      expect(useToastStore.getState().toasts).toHaveLength(0)
    })

    it('uses default duration of 5000ms', () => {
      act(() => {
        useToastStore.getState().addToast({
          type: 'success',
          title: 'Default duration',
        })
      })

      expect(useToastStore.getState().toasts).toHaveLength(1)

      act(() => {
        vi.advanceTimersByTime(4999)
      })
      expect(useToastStore.getState().toasts).toHaveLength(1)

      act(() => {
        vi.advanceTimersByTime(1)
      })
      expect(useToastStore.getState().toasts).toHaveLength(0)
    })

    it('does not auto-remove when duration is 0', () => {
      act(() => {
        useToastStore.getState().addToast({
          type: 'error',
          title: 'Persistent',
          duration: 0,
        })
      })

      act(() => {
        vi.advanceTimersByTime(10000)
      })

      expect(useToastStore.getState().toasts).toHaveLength(1)
    })
  })

  describe('removeToast', () => {
    it('removes toast by id', () => {
      let id: string = ''

      act(() => {
        id = useToastStore.getState().addToast({
          type: 'info',
          title: 'To Remove',
          duration: 0, // Prevent auto-remove
        })
      })

      expect(useToastStore.getState().toasts).toHaveLength(1)

      act(() => {
        useToastStore.getState().removeToast(id)
      })

      expect(useToastStore.getState().toasts).toHaveLength(0)
    })

    it('does nothing if id not found', () => {
      act(() => {
        useToastStore.getState().addToast({
          type: 'info',
          title: 'Keep Me',
          duration: 0,
        })
      })

      act(() => {
        useToastStore.getState().removeToast('non-existent')
      })

      expect(useToastStore.getState().toasts).toHaveLength(1)
    })
  })

  describe('clearToasts', () => {
    it('removes all toasts', () => {
      act(() => {
        useToastStore.getState().addToast({ type: 'info', title: 'One', duration: 0 })
        useToastStore.getState().addToast({ type: 'info', title: 'Two', duration: 0 })
        useToastStore.getState().addToast({ type: 'info', title: 'Three', duration: 0 })
      })

      expect(useToastStore.getState().toasts).toHaveLength(3)

      act(() => {
        useToastStore.getState().clearToasts()
      })

      expect(useToastStore.getState().toasts).toHaveLength(0)
    })
  })

  describe('convenience functions', () => {
    it('toast.success creates success toast', () => {
      act(() => {
        toast.success('Success!', 'Operation completed')
      })

      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].type).toBe('success')
      expect(toasts[0].title).toBe('Success!')
      expect(toasts[0].message).toBe('Operation completed')
    })

    it('toast.error creates error toast with longer duration', () => {
      act(() => {
        toast.error('Error!', 'Something went wrong')
      })

      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].type).toBe('error')

      // Error toasts have 8000ms duration
      act(() => {
        vi.advanceTimersByTime(7999)
      })
      expect(useToastStore.getState().toasts).toHaveLength(1)

      act(() => {
        vi.advanceTimersByTime(1)
      })
      expect(useToastStore.getState().toasts).toHaveLength(0)
    })

    it('toast.warning creates warning toast', () => {
      act(() => {
        toast.warning('Warning!')
      })

      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].type).toBe('warning')
    })

    it('toast.info creates info toast', () => {
      act(() => {
        toast.info('Info')
      })

      const toasts = useToastStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].type).toBe('info')
    })
  })
})
