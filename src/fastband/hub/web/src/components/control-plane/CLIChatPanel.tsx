/**
 * CLI-style Chat Panel for Control Plane
 *
 * A resizable, collapsible terminal-style chat interface
 * that sits at the bottom of the Control Plane dashboard.
 */

import { useState, useRef, useCallback, useEffect, KeyboardEvent } from 'react'
import { clsx } from 'clsx'
import {
  Terminal,
  ChevronUp,
  ChevronDown,
  Send,
  Loader2,
  X,
  Maximize2,
  Minimize2,
} from 'lucide-react'
import { useSidebarStore } from '../../stores/sidebar'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

interface CLIChatPanelProps {
  className?: string
}

const STORAGE_KEY = 'fastband_cli_messages'
const SESSION_KEY = 'fastband_cli_session_id'

// Load messages from localStorage
function loadMessages(): Message[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      // Convert timestamp strings back to Date objects
      return parsed.map((m: Message & { timestamp: string }) => ({
        ...m,
        timestamp: new Date(m.timestamp),
      }))
    }
  } catch {
    // Invalid stored data, return default
  }
  return [
    {
      id: 'welcome',
      role: 'system',
      content: 'Welcome to Fastband CLI. Type a message or command to get started.',
      timestamp: new Date(),
    },
  ]
}

// Get or create session ID
function getSessionId(): string {
  let sessionId = localStorage.getItem(SESSION_KEY)
  if (!sessionId) {
    sessionId = `chat-${crypto.randomUUID()}`
    localStorage.setItem(SESSION_KEY, sessionId)
  }
  return sessionId
}

export function CLIChatPanel({ className }: CLIChatPanelProps) {
  const { isCollapsed: sidebarCollapsed } = useSidebarStore()
  const [isExpanded, setIsExpanded] = useState(false)
  const [isMaximized, setIsMaximized] = useState(false)
  const [height, setHeight] = useState(300)
  const [isDragging, setIsDragging] = useState(false)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>(loadMessages)
  const [sessionId] = useState(getSessionId)

  const inputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const collapsedButtonRef = useRef<HTMLButtonElement>(null)
  const dragStartY = useRef(0)
  const dragStartHeight = useRef(0)

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Save messages to localStorage when they change
  useEffect(() => {
    // Don't save if only the welcome message
    if (messages.length > 1 || messages[0]?.id !== 'welcome') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    }
  }, [messages])

  // Focus input when expanded
  useEffect(() => {
    if (isExpanded) {
      inputRef.current?.focus()
    }
  }, [isExpanded])

  // Handle drag resize
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    dragStartY.current = e.clientY
    dragStartHeight.current = height
  }, [height])

  // Handle keyboard resize
  const handleResizeKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHeight(prev => Math.min(600, prev + 20))
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHeight(prev => Math.max(150, prev - 20))
    }
  }, [])

  useEffect(() => {
    if (!isDragging) return

    let isMounted = true

    const handleMouseMove = (e: MouseEvent) => {
      if (!isMounted) return
      const delta = dragStartY.current - e.clientY
      const newHeight = Math.max(150, Math.min(600, dragStartHeight.current + delta))
      setHeight(newHeight)
    }

    const handleMouseUp = () => {
      if (!isMounted) return
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      isMounted = false
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  // Send message
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          content: userMessage.content,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.content || data.response || data.message || 'No response',
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, assistantMessage])
      } else {
        // Handle error
        const errorMessage: Message = {
          id: crypto.randomUUID(),
          role: 'system',
          content: `Error: ${response.statusText}. Configure an AI provider in Settings.`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errorMessage])
      }
    } catch {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'system',
        content: 'Connection error. Check if the server is running.',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  // Handle key press
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
    if (e.key === 'Escape') {
      setIsExpanded(false)
      // Return focus to collapsed button after panel collapses
      setTimeout(() => collapsedButtonRef.current?.focus(), 100)
    }
  }

  // Format timestamp
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }

  // Collapsed bar
  if (!isExpanded) {
    return (
      <div
        className={clsx(
          'fixed bottom-0 right-0 z-40',
          sidebarCollapsed ? 'left-16' : 'left-64',
          'bg-void-800/95 backdrop-blur-md border-t border-void-600/50',
          'transition-all duration-300',
          className
        )}
        role="region"
        aria-label="CLI Chat Panel - collapsed"
      >
        <button
          ref={collapsedButtonRef}
          onClick={() => setIsExpanded(true)}
          aria-label="Open CLI chat panel"
          aria-expanded={false}
          className="w-full px-4 py-3 flex items-center gap-3 hover:bg-void-700/50 transition-colors"
        >
          <Terminal className="w-5 h-5 text-cyan" aria-hidden="true" />
          <span className="text-sm font-mono text-slate-400">
            fastband@control-plane:~$
          </span>
          <span className="text-xs text-slate-500 ml-auto flex items-center gap-2">
            <span>Click to open CLI</span>
            <ChevronUp className="w-4 h-4" />
          </span>
        </button>
      </div>
    )
  }

  return (
    <div
      ref={panelRef}
      className={clsx(
        'fixed bottom-0 right-0 z-40',
        sidebarCollapsed ? 'left-16' : 'left-64',
        'bg-void-900/98 backdrop-blur-md border-t border-cyan/30',
        'flex flex-col',
        'transition-all duration-300',
        isMaximized ? 'top-16' : '',
        className
      )}
      style={{ height: isMaximized ? 'calc(100vh - 4rem)' : `${height}px` }}
    >
      {/* Resize handle */}
      {!isMaximized && (
        <div
          onMouseDown={handleDragStart}
          onKeyDown={handleResizeKeyDown}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize chat panel. Use arrow keys to adjust height."
          aria-valuenow={height}
          aria-valuemin={150}
          aria-valuemax={600}
          tabIndex={0}
          className={clsx(
            'absolute -top-1 left-0 right-0 h-3 cursor-ns-resize',
            'hover:bg-cyan/20 focus:bg-cyan/20 focus:outline-none transition-colors',
            isDragging && 'bg-cyan/30'
          )}
        >
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-1 rounded-full bg-void-600" />
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-void-600/50 bg-void-800/80">
        <div className="flex items-center gap-3">
          <Terminal className="w-5 h-5 text-cyan" />
          <span className="text-sm font-display font-semibold text-slate-200">
            Fastband CLI
          </span>
          <span className="text-xs font-mono text-slate-500">
            {messages.length - 1} messages
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            className="btn-icon p-1.5"
            title={isMaximized ? 'Restore' : 'Maximize'}
          >
            {isMaximized ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={() => setIsExpanded(false)}
            className="btn-icon p-1.5"
            title="Minimize"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setIsExpanded(false)
              // Clear messages and localStorage
              const welcomeMessage = {
                id: 'welcome',
                role: 'system' as const,
                content: 'Welcome to Fastband CLI. Type a message or command to get started.',
                timestamp: new Date(),
              }
              setMessages([welcomeMessage])
              localStorage.removeItem(STORAGE_KEY)
              // Note: We keep the session ID so backend conversation history persists
            }}
            className="btn-icon p-1.5 hover:text-error"
            title="Close and clear"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-3"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.map((msg) => (
          <div key={msg.id} className="flex flex-col">
            <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
              <span className={clsx(
                'font-semibold',
                msg.role === 'user' && 'text-cyan',
                msg.role === 'assistant' && 'text-magenta',
                msg.role === 'system' && 'text-warning'
              )}>
                {msg.role === 'user' ? 'you' : msg.role === 'assistant' ? 'fastband' : 'system'}
              </span>
              <span>{formatTime(msg.timestamp)}</span>
            </div>
            <div
              className={clsx(
                'pl-2 border-l-2',
                msg.role === 'user' && 'border-cyan/40 text-slate-300',
                msg.role === 'assistant' && 'border-magenta/40 text-slate-200',
                msg.role === 'system' && 'border-warning/40 text-slate-400 italic'
              )}
            >
              <pre className="whitespace-pre-wrap break-words">{msg.content}</pre>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 className="w-4 h-4 animate-spin text-magenta" />
            <span className="text-xs">Processing...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="flex items-center gap-3 px-4 py-3 border-t border-void-600/50 bg-void-800/50">
        <span className="text-cyan font-mono text-sm">$</span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message or command..."
          disabled={isLoading}
          className={clsx(
            'flex-1 bg-transparent border-none outline-none',
            'font-mono text-sm text-slate-200 placeholder-slate-600',
            'disabled:opacity-50'
          )}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || isLoading}
          className={clsx(
            'p-2 rounded-lg transition-all',
            input.trim() && !isLoading
              ? 'bg-cyan/20 text-cyan hover:bg-cyan/30'
              : 'bg-void-700 text-slate-600 cursor-not-allowed'
          )}
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  )
}
