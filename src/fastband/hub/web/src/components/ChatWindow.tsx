import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Bot, User, Wrench, Sparkles, Zap, Copy, Check } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
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

  const { messages, addMessage } = useChatStore()
  const { sessionId, conversationId } = useSessionStore()

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent, scrollToBottom])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`
    }
  }, [input])

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
                fullContent += `\n\n> 🔧 **Tool:** ${data.tool_name}\n\n`
                setStreamingContent(fullContent)
              } else if (data.type === 'done') {
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
            } catch {
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
        content: 'Sorry, I encountered an error processing your request. Please try again.',
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
    <div className="flex flex-col h-full bg-void-900 bg-grid relative">
      {/* Radial glow effect */}
      <div className="radial-glow absolute inset-0 pointer-events-none" />

      {/* Empty state */}
      {messages.length === 0 && !isStreaming && (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md animate-in">
            <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-cyan/20 to-magenta/20 border border-cyan/30 flex items-center justify-center logo-glow">
              <Zap className="w-8 h-8 text-cyan" />
            </div>
            <h2 className="text-2xl font-display font-bold text-slate-100 mb-2">
              Welcome to <span className="text-gradient">Fastband Hub</span>
            </h2>
            <p className="text-slate-400 mb-6">
              Your AI-powered development command center. Ask me anything about your project.
            </p>
            <div className="grid grid-cols-2 gap-3 text-left">
              {[
                { icon: '📁', text: 'Analyze your codebase' },
                { icon: '🐛', text: 'Debug issues' },
                { icon: '✨', text: 'Generate code' },
                { icon: '📖', text: 'Explain concepts' },
              ].map((item, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-void-800/50 border border-void-600/50 hover:border-cyan/30 transition-colors cursor-pointer animate-in-delayed"
                  style={{ animationDelay: `${i * 0.05}s` }}
                >
                  <span className="text-lg mr-2">{item.icon}</span>
                  <span className="text-sm text-slate-300">{item.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      {(messages.length > 0 || isStreaming) && (
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              isFirst={index === 0}
            />
          ))}

          {/* Streaming message */}
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

          {/* Typing indicator */}
          {isStreaming && !streamingContent && (
            <div className="flex items-center gap-4 max-w-4xl mx-auto animate-in">
              <div className="avatar avatar-assistant w-9 h-9 flex-shrink-0">
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="message-assistant px-4 py-3">
                <div className="typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-void-600/50 bg-void-800/30 backdrop-blur-sm p-4">
        <div className="max-w-4xl mx-auto">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about your project..."
              className={clsx(
                'w-full resize-none rounded-xl border bg-void-800/80 px-4 py-3 pr-14',
                'text-slate-100 placeholder-slate-500 font-body',
                'min-h-[52px] max-h-[200px]',
                'transition-all duration-200 ease-out',
                'focus:outline-none focus:ring-2 focus:ring-cyan/30',
                isStreaming
                  ? 'border-void-600 opacity-60'
                  : 'border-void-600 hover:border-cyan/30 focus:border-cyan/50'
              )}
              rows={1}
              disabled={isStreaming}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isStreaming}
              className={clsx(
                'absolute right-2 bottom-2 p-2.5 rounded-lg',
                'transition-all duration-200 ease-out',
                input.trim() && !isStreaming
                  ? 'bg-cyan text-void-900 hover:shadow-glow-cyan hover:scale-105 active:scale-95'
                  : 'bg-void-700 text-slate-500 cursor-not-allowed'
              )}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-2xs text-slate-500 mt-2 text-center">
            Press <kbd className="px-1.5 py-0.5 rounded bg-void-700 text-slate-400 font-mono">Enter</kbd> to send,{' '}
            <kbd className="px-1.5 py-0.5 rounded bg-void-700 text-slate-400 font-mono">Shift+Enter</kbd> for new line
          </p>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  isStreaming = false,
  isFirst: _isFirst = false,
}: {
  message: Message
  isStreaming?: boolean
  isFirst?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={clsx(
        'flex gap-4 max-w-4xl mx-auto animate-in',
        isUser && 'flex-row-reverse'
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0',
          'transition-all duration-200',
          isUser
            ? 'avatar-user'
            : isTool
              ? 'bg-gradient-to-br from-warning/20 to-warning/5 border border-warning/30 text-warning'
              : 'avatar-assistant'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4" />
        ) : isTool ? (
          <Wrench className="w-4 h-4" />
        ) : (
          <Bot className="w-4 h-4" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div
          className={clsx(
            'rounded-2xl px-4 py-3 max-w-[90%] relative group',
            isUser
              ? 'message-user ml-auto'
              : isTool
                ? 'message-tool'
                : 'message-assistant'
          )}
        >
          {/* Copy button */}
          {!isUser && !isStreaming && (
            <button
              onClick={handleCopy}
              className={clsx(
                'absolute -right-2 -top-2 p-1.5 rounded-lg',
                'bg-void-700 border border-void-600 text-slate-400',
                'opacity-0 group-hover:opacity-100 transition-all duration-150',
                'hover:text-cyan hover:border-cyan/30'
              )}
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-success" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          )}

          {/* Markdown content */}
          <div className="prose-terminal">
            <ReactMarkdown
              components={{
                code({ node, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '')
                  const isInline = !match

                  if (isInline) {
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    )
                  }

                  return (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      customStyle={{
                        margin: 0,
                        borderRadius: '0.5rem',
                        background: '#0a0f1a',
                        border: '1px solid rgba(0, 212, 255, 0.1)',
                      }}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Tool calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-3 pt-3 border-t border-void-600/50 space-y-1">
              {message.toolCalls.map((tc) => (
                <div
                  key={tc.toolId}
                  className="flex items-center gap-2 text-xs text-slate-400"
                >
                  <Wrench className="w-3 h-3 text-warning" />
                  <span className="font-mono">{tc.toolName}</span>
                </div>
              ))}
            </div>
          )}

          {/* Streaming cursor */}
          {isStreaming && (
            <span className="cursor-blink" />
          )}
        </div>

        {/* Timestamp */}
        <p
          className={clsx(
            'text-2xs text-slate-600 mt-1.5',
            isUser ? 'text-right' : 'text-left'
          )}
        >
          {message.createdAt.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  )
}
