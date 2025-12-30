import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import {
  MessageSquare,
  Plus,
  Trash2,
  MoreHorizontal,
  Search,
  Sparkles,
} from 'lucide-react'
import { useConversationsStore, Conversation } from '../stores/conversations'
import { useSessionStore } from '../stores/session'
import { useChatStore } from '../stores/chat'

export function ConversationSidebar() {
  const [searchQuery, setSearchQuery] = useState('')
  const [contextMenu, setContextMenu] = useState<string | null>(null)

  const {
    conversations,
    activeId,
    isLoading,
    fetchConversations,
    createConversation,
    setActive,
    deleteConversation,
  } = useConversationsStore()

  const { setConversation } = useSessionStore()
  const { clearMessages } = useChatStore()

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  const handleNewChat = async () => {
    try {
      const conversation = await createConversation()
      setConversation(conversation.id)
      clearMessages()
    } catch (error) {
      console.error('Failed to create conversation:', error)
    }
  }

  const handleSelectConversation = (conversation: Conversation) => {
    setActive(conversation.id)
    setConversation(conversation.id)
    // Load messages for this conversation
    loadConversationMessages(conversation.id)
  }

  const loadConversationMessages = async (id: string) => {
    try {
      const response = await fetch(`/api/conversations/${id}`)
      if (!response.ok) return

      const data = await response.json()
      clearMessages()

      // Add messages to the store
      if (data.messages) {
        const { addMessage } = useChatStore.getState()
        data.messages.forEach((msg: any) => {
          addMessage({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            createdAt: new Date(msg.created_at),
          })
        })
      }
    } catch (error) {
      console.error('Failed to load conversation:', error)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await deleteConversation(id)
      setContextMenu(null)
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    }
  }

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Group conversations by date
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)

  const groupedConversations = {
    today: filteredConversations.filter(
      (c) => c.updatedAt.toDateString() === today.toDateString()
    ),
    yesterday: filteredConversations.filter(
      (c) => c.updatedAt.toDateString() === yesterday.toDateString()
    ),
    lastWeek: filteredConversations.filter(
      (c) =>
        c.updatedAt > lastWeek &&
        c.updatedAt.toDateString() !== today.toDateString() &&
        c.updatedAt.toDateString() !== yesterday.toDateString()
    ),
    older: filteredConversations.filter((c) => c.updatedAt <= lastWeek),
  }

  return (
    <div className="flex flex-col h-full bg-void-800/50 border-r border-void-600/50">
      {/* Header with New Chat button */}
      <div className="p-3 border-b border-void-600/50">
        <button
          onClick={handleNewChat}
          className="btn-primary w-full flex items-center justify-center gap-2 group"
        >
          <Plus className="w-4 h-4 transition-transform group-hover:rotate-90" />
          <span>New Chat</span>
          <Sparkles className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity text-void-900" />
        </button>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-void-600/30">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-void-900/50 border border-void-600/50 rounded-lg
                       text-sm text-slate-200 placeholder-slate-500
                       focus:outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20
                       transition-all duration-200"
          />
        </div>
      </div>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto scrollbar-hide">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="skeleton h-12 rounded-lg" />
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="p-6 text-center">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-void-700/50 flex items-center justify-center">
              <MessageSquare className="w-6 h-6 text-slate-500" />
            </div>
            <p className="text-slate-400 text-sm">No conversations yet</p>
            <p className="text-slate-500 text-xs mt-1">
              Start a new chat to begin
            </p>
          </div>
        ) : (
          <div className="p-2 space-y-4">
            {groupedConversations.today.length > 0 && (
              <ConversationGroup
                title="Today"
                conversations={groupedConversations.today}
                activeId={activeId}
                contextMenu={contextMenu}
                setContextMenu={setContextMenu}
                onSelect={handleSelectConversation}
                onDelete={handleDelete}
              />
            )}

            {groupedConversations.yesterday.length > 0 && (
              <ConversationGroup
                title="Yesterday"
                conversations={groupedConversations.yesterday}
                activeId={activeId}
                contextMenu={contextMenu}
                setContextMenu={setContextMenu}
                onSelect={handleSelectConversation}
                onDelete={handleDelete}
              />
            )}

            {groupedConversations.lastWeek.length > 0 && (
              <ConversationGroup
                title="Last 7 Days"
                conversations={groupedConversations.lastWeek}
                activeId={activeId}
                contextMenu={contextMenu}
                setContextMenu={setContextMenu}
                onSelect={handleSelectConversation}
                onDelete={handleDelete}
              />
            )}

            {groupedConversations.older.length > 0 && (
              <ConversationGroup
                title="Older"
                conversations={groupedConversations.older}
                activeId={activeId}
                contextMenu={contextMenu}
                setContextMenu={setContextMenu}
                onSelect={handleSelectConversation}
                onDelete={handleDelete}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface ConversationGroupProps {
  title: string
  conversations: Conversation[]
  activeId: string | null
  contextMenu: string | null
  setContextMenu: (id: string | null) => void
  onSelect: (conversation: Conversation) => void
  onDelete: (id: string, e: React.MouseEvent) => void
}

function ConversationGroup({
  title,
  conversations,
  activeId,
  contextMenu,
  setContextMenu,
  onSelect,
  onDelete,
}: ConversationGroupProps) {
  return (
    <div>
      <h3 className="px-3 py-1.5 text-2xs font-medium text-slate-500 uppercase tracking-wider">
        {title}
      </h3>
      <div className="space-y-0.5">
        {conversations.map((conversation) => (
          <ConversationItem
            key={conversation.id}
            conversation={conversation}
            isActive={activeId === conversation.id}
            showMenu={contextMenu === conversation.id}
            onToggleMenu={() =>
              setContextMenu(
                contextMenu === conversation.id ? null : conversation.id
              )
            }
            onSelect={() => onSelect(conversation)}
            onDelete={(e) => onDelete(conversation.id, e)}
          />
        ))}
      </div>
    </div>
  )
}

interface ConversationItemProps {
  conversation: Conversation
  isActive: boolean
  showMenu: boolean
  onToggleMenu: () => void
  onSelect: () => void
  onDelete: (e: React.MouseEvent) => void
}

function ConversationItem({
  conversation,
  isActive,
  showMenu,
  onToggleMenu,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  return (
    <div
      onClick={onSelect}
      className={clsx(
        'group relative flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer',
        'transition-all duration-150 ease-out',
        isActive
          ? 'bg-cyan/10 border-l-2 border-cyan'
          : 'hover:bg-void-700/70 border-l-2 border-transparent'
      )}
    >
      {/* Icon */}
      <div
        className={clsx(
          'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0',
          'transition-all duration-200',
          isActive
            ? 'bg-cyan/20 text-cyan'
            : 'bg-void-700/50 text-slate-400 group-hover:text-slate-300'
        )}
      >
        <MessageSquare className="w-3.5 h-3.5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p
          className={clsx(
            'text-sm font-medium truncate transition-colors',
            isActive ? 'text-cyan' : 'text-slate-200'
          )}
        >
          {conversation.title}
        </p>
        <p className="text-2xs text-slate-500 truncate">
          {conversation.messageCount} messages
        </p>
      </div>

      {/* Actions */}
      <div
        className={clsx(
          'flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity',
          showMenu && 'opacity-100'
        )}
      >
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggleMenu()
          }}
          className="p-1.5 rounded-md hover:bg-void-600/50 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </div>

      {/* Context menu */}
      {showMenu && (
        <div
          className="absolute right-2 top-full mt-1 z-10 py-1 bg-void-800 border border-void-600 rounded-lg shadow-lg animate-in"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={onDelete}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-400 hover:bg-red-500/10 w-full transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
