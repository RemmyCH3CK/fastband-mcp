/**
 * WebSocket hook for Control Plane real-time updates.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { WSMessage, SubscriptionType } from '../types/controlPlane'

interface UseWebSocketOptions {
  subscriptions?: SubscriptionType[]
  onMessage?: (message: WSMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  autoReconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

interface UseWebSocketReturn {
  isConnected: boolean
  connectionId: string | null
  send: (message: WSMessage) => void
  reconnect: () => void
  disconnect: () => void
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    subscriptions = ['all'],
    onMessage,
    onConnect,
    onDisconnect,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [connectionId, setConnectionId] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null)

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const subsParam = subscriptions.join(',')
    return `${protocol}//${host}/api/control-plane/ws?subscriptions=${subsParam}`
  }, [subscriptions])

  const connect = useCallback(() => {
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    const url = getWebSocketUrl()
    console.log('[WebSocket] Connecting to:', url)

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[WebSocket] Connected')
      setIsConnected(true)
      reconnectAttempts.current = 0
      onConnect?.()
    }

    ws.onclose = (event) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason)
      setIsConnected(false)
      setConnectionId(null)
      onDisconnect?.()

      // Auto-reconnect logic
      if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
        const delay = Math.min(
          reconnectInterval * Math.pow(2, reconnectAttempts.current),
          30000 // Max 30 seconds
        )
        console.log(`[WebSocket] Reconnecting in ${delay}ms...`)
        reconnectTimeout.current = setTimeout(() => {
          reconnectAttempts.current++
          connect()
        }, delay)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSMessage
        console.log('[WebSocket] Message:', message.type)

        // Handle system messages
        if (message.type === 'system:connected') {
          const connId = (message.data as { connection_id?: string }).connection_id
          if (connId) {
            setConnectionId(connId)
          }
        } else if (message.type === 'system:ping') {
          // Respond to ping with pong
          send({ type: 'system:pong', timestamp: new Date().toISOString(), data: {} })
        }

        // Forward to handler
        onMessage?.(message)
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error)
      }
    }
  }, [
    getWebSocketUrl,
    onConnect,
    onDisconnect,
    onMessage,
    autoReconnect,
    reconnectInterval,
    maxReconnectAttempts,
  ])

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current)
      reconnectTimeout.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
    setConnectionId(null)
  }, [])

  const send = useCallback((message: WSMessage) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('[WebSocket] Cannot send - not connected')
    }
  }, [])

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0
    disconnect()
    connect()
  }, [connect, disconnect])

  // Connect on mount
  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    connectionId,
    send,
    reconnect,
    disconnect,
  }
}
