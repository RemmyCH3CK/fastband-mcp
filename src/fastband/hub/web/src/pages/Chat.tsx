import { useEffect } from 'react'
import { useAuthStore } from '../stores/auth'
import { useSessionStore } from '../stores/session'
import { ChatWindow } from '../components/ChatWindow'

export function Chat() {
  const { user } = useAuthStore()
  const { sessionId, createSession } = useSessionStore()

  useEffect(() => {
    if (user && !sessionId) {
      createSession(user.id)
    }
  }, [user, sessionId, createSession])

  if (!sessionId) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-400">Initializing session...</p>
        </div>
      </div>
    )
  }

  return <ChatWindow />
}
