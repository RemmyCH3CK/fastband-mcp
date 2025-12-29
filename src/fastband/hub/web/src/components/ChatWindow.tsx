import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Bot, User, Wrench } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { clsx } from 'clsx'
import { useChatStore } from '../stores/chat'
import { useSessionStore } from '../stores/session'

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

export function ChatWindow() {
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const { messages, addMessage, updateLastMessage } = useChatStore()
  const { sessionId, conversationId } = useSessionStore()

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent, scrollToBottom])

  const sendMessage = async () => {
    if (!input.trim() || isStreaming || !sessionId) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      createdAt: new Date(),
    }

    addMessage(userMessage)
    setInput('')
    setIsStreaming(true)
    setStreamingContent('')

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          content: userMessage.content,
          conversation_id: conversationId,
          stream: true,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to send message')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No response body')
      }

      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'content') {
                fullContent += data.content
                setStreamingContent(fullContent)
              } else if (data.type === 'tool') {
                // Tool execution indicator
                fullContent += `\n[Tool: ${data.tool_name}]\n`
                setStreamingContent(fullContent)
              } else if (data.type === 'done') {
                // Stream complete
                const assistantMessage: Message = {
                  id: data.message_id || crypto.randomUUID(),
                  role: 'assistant',
                  content: fullContent,
                  createdAt: new Date(),
                }
                addMessage(assistantMessage)
              } else if (data.type === 'error') {
                throw new Error(data.error)
              }
            } catch (e) {
              // Ignore parse errors for partial data
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        createdAt: new Date(),
      }
      addMessage(errorMessage)
    } finally {
      setIsStreaming(false)
      setStreamingContent('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {/* Streaming indicator */}
        {isStreaming && streamingContent && (
          <MessageBubble
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingContent,
              createdAt: new Date(),
            }}
            isStreaming
          />
        )}

        {/* Loading indicator */}
        {isStreaming && !streamingContent && (
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-700 p-4">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything about your project..."
            className={clsx(
              'flex-1 resize-none rounded-lg border border-gray-600 bg-gray-800 px-4 py-3',
              'text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none',
              'min-h-[52px] max-h-[200px]'
            )}
            rows={1}
            disabled={isStreaming}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            className={clsx(
              'rounded-lg px-4 py-2 font-medium transition-colors',
              'bg-blue-600 text-white hover:bg-blue-700',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {isStreaming ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  isStreaming = false,
}: {
  message: Message
  isStreaming?: boolean
}) {
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'

  return (
    <div
      className={clsx(
        'flex gap-3 max-w-4xl mx-auto',
        isUser && 'flex-row-reverse'
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isUser ? 'bg-blue-600' : isTool ? 'bg-yellow-600' : 'bg-green-600'
        )}
      >
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : isTool ? (
          <Wrench className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>

      {/* Content */}
      <div
        className={clsx(
          'rounded-lg px-4 py-3 max-w-[80%]',
          isUser
            ? 'bg-blue-600 text-white'
            : isTool
              ? 'bg-yellow-900/50 text-yellow-100 border border-yellow-700'
              : 'bg-gray-800 text-gray-100'
        )}
      >
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.toolCalls.map((tc) => (
              <div
                key={tc.toolId}
                className="text-xs text-gray-400 flex items-center gap-1"
              >
                <Wrench className="w-3 h-3" />
                <span>{tc.toolName}</span>
              </div>
            ))}
          </div>
        )}

        {/* Streaming cursor */}
        {isStreaming && (
          <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1" />
        )}
      </div>
    </div>
  )
}
