import { ReactNode, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  MessageSquare,
  Settings,
  LogOut,
  Menu,
  X,
  Zap,
  FileCode,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Shield,
  Archive,
  Ticket,
  BookOpen,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react'
import { useAuthStore } from '../stores/auth'
import { useSessionStore } from '../stores/session'
import { useSidebarStore } from '../stores/sidebar'
import { ConversationSidebar } from './ConversationSidebar'

interface LayoutProps {
  children: ReactNode
  showConversationSidebar?: boolean
}

const navigation = [
  { name: 'Control Plane', href: '/', icon: Shield },
  { name: 'Tickets', href: '/tickets', icon: Ticket },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Analyze', href: '/analyze', icon: FileCode },
  { name: 'Backups', href: '/backups', icon: Archive },
  { name: 'Agent Bible', href: '/bible', icon: BookOpen },
  { name: 'Usage', href: '/usage', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Layout({ children, showConversationSidebar = true }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [conversationSidebarOpen, setConversationSidebarOpen] = useState(true)
  const { isCollapsed, toggleCollapsed } = useSidebarStore()
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuthStore()
  const { tier, clearSession } = useSessionStore()

  const handleSignOut = async () => {
    await signOut()
    clearSession()
    navigate('/login')
  }

  const tierConfig = {
    free: { label: 'Free', className: 'badge-free' },
    pro: { label: 'Pro', className: 'badge-pro' },
    enterprise: { label: 'Enterprise', className: 'badge-enterprise' },
  }[tier]

  const isChat = location.pathname === '/chat' || location.pathname.startsWith('/conversation/')
  const shouldShowConversationSidebar = showConversationSidebar && isChat

  return (
    <div className="h-screen flex bg-void-900">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden animate-in"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Navigation Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 bg-void-800/95 backdrop-blur-md border-r border-void-600/50',
          'transform transition-all duration-300 ease-out lg:translate-x-0 lg:static lg:z-auto',
          isCollapsed ? 'w-16' : 'w-64',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className={clsx(
            'flex items-center border-b border-void-600/50',
            isCollapsed ? 'px-2 py-4 justify-center' : 'gap-3 px-4 py-5'
          )}>
            <div className={clsx(
              'rounded-xl bg-gradient-to-br from-cyan/20 to-magenta/20 border border-cyan/30 flex items-center justify-center logo-glow',
              isCollapsed ? 'w-10 h-10' : 'w-11 h-11'
            )}>
              <Zap className={clsx('text-cyan', isCollapsed ? 'w-5 h-5' : 'w-6 h-6')} />
            </div>
            {!isCollapsed && (
              <>
                <div className="flex-1">
                  <h1 className="text-lg font-display font-bold text-gradient">Fastband</h1>
                  <span className={clsx('badge', tierConfig.className)}>
                    {tierConfig.label}
                  </span>
                </div>
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="lg:hidden btn-icon"
                >
                  <X className="w-5 h-5" />
                </button>
              </>
            )}
          </div>

          {/* Navigation */}
          <nav
            className={clsx(
              'flex-1 py-4 space-y-1',
              isCollapsed ? 'px-2' : 'px-3'
            )}
            aria-label="Main navigation"
          >
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  title={isCollapsed ? item.name : undefined}
                  aria-current={isActive ? 'page' : undefined}
                  className={clsx(
                    'flex items-center rounded-lg transition-all duration-200',
                    isCollapsed ? 'justify-center p-2.5' : 'gap-3 px-3 py-2.5',
                    isActive
                      ? 'bg-cyan/10 text-cyan border-l-2 border-cyan'
                      : 'text-slate-400 hover:bg-void-700/50 hover:text-slate-200 border-l-2 border-transparent'
                  )}
                >
                  <item.icon className={clsx('w-5 h-5 flex-shrink-0', isActive && 'text-cyan')} />
                  {!isCollapsed && <span className="font-medium">{item.name}</span>}
                </Link>
              )
            })}
          </nav>

          {/* Collapse toggle (desktop only) */}
          <div className={clsx(
            'hidden lg:flex border-t border-void-600/30',
            isCollapsed ? 'px-2 py-3 justify-center' : 'px-3 py-3'
          )}>
            <button
              onClick={toggleCollapsed}
              className={clsx(
                'btn-icon text-slate-500 hover:text-cyan transition-colors',
                isCollapsed ? 'p-2' : 'w-full flex items-center gap-2 px-3 py-2'
              )}
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCollapsed ? (
                <PanelLeft className="w-5 h-5" />
              ) : (
                <>
                  <PanelLeftClose className="w-5 h-5" />
                  <span className="text-sm">Collapse</span>
                </>
              )}
            </button>
          </div>

          {/* User section */}
          <div className={clsx(
            'border-t border-void-600/50',
            isCollapsed ? 'p-2' : 'p-4'
          )}>
            <div className={clsx(
              'flex items-center',
              isCollapsed ? 'flex-col gap-2' : 'gap-3'
            )}>
              <div className={clsx(
                'avatar avatar-user',
                isCollapsed ? 'w-8 h-8' : 'w-10 h-10'
              )}>
                <span className={clsx('font-medium', isCollapsed ? 'text-xs' : 'text-sm')}>
                  {user?.email?.[0]?.toUpperCase() || '?'}
                </span>
              </div>
              {!isCollapsed && (
                <>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-100 truncate">
                      {user?.email || 'Guest'}
                    </p>
                    <p className="text-2xs text-slate-500">
                      {tier.charAt(0).toUpperCase() + tier.slice(1)} Plan
                    </p>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="btn-icon text-slate-400 hover:text-error"
                    title="Sign out"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </>
              )}
              {isCollapsed && (
                <button
                  onClick={handleSignOut}
                  className="btn-icon text-slate-400 hover:text-error p-1.5"
                  title="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Conversation Sidebar (only on chat page) */}
      {shouldShowConversationSidebar && (
        <div
          className={clsx(
            'hidden lg:flex flex-col bg-void-800/50 border-r border-void-600/30',
            'transition-all duration-300 ease-out',
            conversationSidebarOpen ? 'w-72' : 'w-0'
          )}
        >
          {conversationSidebarOpen && <ConversationSidebar />}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 px-4 py-3 bg-void-800/80 backdrop-blur-sm border-b border-void-600/50">
          <button
            onClick={() => setSidebarOpen(true)}
            className="btn-icon"
          >
            <Menu className="w-6 h-6" />
          </button>
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-cyan" />
            <h1 className="text-lg font-display font-bold text-gradient">Fastband</h1>
          </div>
        </header>

        {/* Toggle conversation sidebar button (desktop only, chat page only) */}
        {shouldShowConversationSidebar && (
          <button
            onClick={() => setConversationSidebarOpen(!conversationSidebarOpen)}
            className={clsx(
              'hidden lg:flex absolute left-0 top-1/2 -translate-y-1/2 z-10',
              'w-5 h-12 items-center justify-center',
              'bg-void-700/80 hover:bg-void-600 border border-void-600 rounded-r-lg',
              'text-slate-400 hover:text-cyan transition-all duration-200',
              conversationSidebarOpen ? '-translate-x-0.5' : 'translate-x-0'
            )}
            title={conversationSidebarOpen ? 'Hide conversations' : 'Show conversations'}
          >
            {conversationSidebarOpen ? (
              <ChevronLeft className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
