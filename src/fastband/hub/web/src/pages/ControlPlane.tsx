/**
 * Control Plane Dashboard - Mission control for multi-agent coordination.
 *
 * This is the main dashboard showing:
 * - Real-time agent activity
 * - Operations log timeline
 * - Hold/clearance directives
 * - Active tickets
 */

import { useEffect, useCallback, useState, useMemo } from 'react'
import { clsx } from 'clsx'
import {
  RefreshCw,
  Radio,
  Shield,
  Zap,
  MessageSquare,
  Keyboard,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useControlPlaneStore } from '../stores/controlPlane'
import { useWebSocket } from '../hooks/useWebSocket'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import {
  MetricsBar,
  AgentStatusGrid,
  OpsLogTimeline,
  DirectivePanel,
  TicketsPanel,
  HoldModal,
  ClearanceModal,
  AgentDetailModal,
  TicketDetailModal,
} from '../components/control-plane'
import type { WSMessage, AgentActivity, TicketSummary } from '../types/controlPlane'
import { toast } from '../stores/toast'

export function ControlPlane() {
  const {
    agents,
    opsLogEntries,
    activeTickets,
    directiveState,
    metrics,
    lastUpdated,
    isLoading,
    error,
    wsConnected,
    setDashboardState,
    setWSConnected,
    setLoading,
    setError,
    handleWSMessage,
  } = useControlPlaneStore()

  // Modal state
  const [isHoldModalOpen, setIsHoldModalOpen] = useState(false)
  const [isClearanceModalOpen, setIsClearanceModalOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentActivity | null>(null)
  const [selectedTicket, setSelectedTicket] = useState<TicketSummary | null>(null)
  const [showShortcutsHelp, setShowShortcutsHelp] = useState(false)

  // Keyboard shortcuts
  const shortcuts = useMemo(
    () => [
      {
        key: 'h',
        action: () => setIsHoldModalOpen(true),
        description: 'Issue hold directive',
      },
      {
        key: 'c',
        action: () => setIsClearanceModalOpen(true),
        description: 'Grant clearance',
      },
      {
        key: 'r',
        action: () => fetchDashboard(),
        description: 'Refresh dashboard',
      },
      {
        key: '?',
        action: () => setShowShortcutsHelp((prev) => !prev),
        description: 'Toggle shortcuts help',
      },
      {
        key: 'Escape',
        action: () => {
          setIsHoldModalOpen(false)
          setIsClearanceModalOpen(false)
          setSelectedAgent(null)
          setSelectedTicket(null)
          setShowShortcutsHelp(false)
        },
        description: 'Close modals',
      },
    ],
    []
  )

  useKeyboardShortcuts({ shortcuts })

  // Fetch initial dashboard state
  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/control-plane/dashboard')
      if (!response.ok) {
        throw new Error(`Failed to fetch dashboard: ${response.statusText}`)
      }
      const data = await response.json()
      setDashboardState(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [setDashboardState, setLoading, setError])

  // Handle incoming WebSocket messages
  const onWSMessage = useCallback(
    (message: WSMessage) => {
      handleWSMessage(message)
    },
    [handleWSMessage]
  )

  // WebSocket connection
  const { isConnected } = useWebSocket({
    subscriptions: ['all'],
    onMessage: onWSMessage,
    onConnect: () => setWSConnected(true),
    onDisconnect: () => setWSConnected(false),
    autoReconnect: true,
  })

  // Fetch dashboard on mount
  useEffect(() => {
    fetchDashboard()
  }, [fetchDashboard])

  // Handle issuing a hold directive
  const handleIssueHold = useCallback(
    async (data: {
      issuing_agent: string
      affected_agents: string[]
      tickets: string[]
      reason: string
    }) => {
      const response = await fetch('/api/control-plane/hold', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issuing_agent: data.issuing_agent,
          affected_agents: data.affected_agents,
          tickets: data.tickets.length > 0 ? data.tickets : null,
          reason: data.reason,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || 'Failed to issue hold')
      }

      // Show success toast
      toast.warning(
        'Hold Issued',
        `${data.affected_agents.join(', ')} must pause work`
      )

      // Refresh dashboard to get updated state
      await fetchDashboard()
    },
    [fetchDashboard]
  )

  // Handle granting clearance
  const handleGrantClearance = useCallback(
    async (data: {
      granting_agent: string
      granted_to: string[]
      tickets: string[]
      reason: string
    }) => {
      const response = await fetch('/api/control-plane/clearance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          granting_agent: data.granting_agent,
          granted_to: data.granted_to,
          tickets: data.tickets,
          reason: data.reason,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || 'Failed to grant clearance')
      }

      // Show success toast
      toast.success(
        'Clearance Granted',
        `${data.granted_to.join(', ')} cleared for tickets #${data.tickets.join(', #')}`
      )

      // Refresh dashboard to get updated state
      await fetchDashboard()
    },
    [fetchDashboard]
  )

  // Sync WebSocket connection status
  useEffect(() => {
    setWSConnected(isConnected)
  }, [isConnected, setWSConnected])

  return (
    <div className="flex flex-col h-full bg-void-900 bg-grid bg-noise scan-line">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-void-600/50 bg-void-800/80 backdrop-blur-sm header-glow-line">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan/20 to-magenta/20 border border-cyan/30 flex items-center justify-center logo-glow">
              <Shield className="w-5 h-5 text-cyan" />
            </div>
            <div>
              <h1 className="text-xl font-display font-bold text-gradient">
                Control Plane
              </h1>
              <p className="text-xs text-slate-500">Agent Coordination Center</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Keyboard shortcuts help */}
          <button
            onClick={() => setShowShortcutsHelp((prev) => !prev)}
            className={clsx(
              'btn-icon',
              showShortcutsHelp && 'bg-cyan/20 border-cyan/50'
            )}
            title="Keyboard shortcuts (?)"
          >
            <Keyboard className="w-5 h-5" />
          </button>

          {/* Refresh button */}
          <button
            onClick={fetchDashboard}
            disabled={isLoading}
            className="btn-icon"
            title="Refresh dashboard (R)"
          >
            <RefreshCw
              className={clsx('w-5 h-5', isLoading && 'animate-spin')}
            />
          </button>

          {/* Chat link */}
          <Link
            to="/chat"
            className="btn-secondary flex items-center gap-2 py-2"
          >
            <MessageSquare className="w-4 h-4" />
            <span>Chat</span>
          </Link>
        </div>
      </header>

      {/* Metrics Bar */}
      <MetricsBar
        metrics={metrics}
        wsConnected={wsConnected}
        lastUpdated={lastUpdated}
      />

      {/* Error banner */}
      {error && (
        <div className="mx-6 mt-4 p-4 rounded-lg bg-error/10 border border-error/30 text-error">
          <p className="text-sm">{error}</p>
          <button
            onClick={fetchDashboard}
            className="text-xs underline mt-1 hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Keyboard shortcuts help overlay - HUD style */}
      {showShortcutsHelp && (
        <div className="absolute top-20 right-6 z-50 w-72 shortcuts-hud p-5 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-display font-semibold text-slate-100 flex items-center gap-2">
              <Keyboard className="w-4 h-4 text-cyan" />
              <span className="text-gradient">Keyboard Shortcuts</span>
            </h3>
            <button
              onClick={() => setShowShortcutsHelp(false)}
              className="kbd-key !px-1.5 !py-0.5"
            >
              ESC
            </button>
          </div>
          <div className="space-y-3 stagger-fade-in">
            {shortcuts
              .filter((s) => s.key !== 'Escape')
              .map((shortcut) => (
                <div
                  key={shortcut.key}
                  className="flex items-center justify-between text-sm group"
                >
                  <span className="text-slate-400 group-hover:text-slate-200 transition-colors">
                    {shortcut.description}
                  </span>
                  <kbd className="kbd-key">
                    {shortcut.key === '?' ? '?' : shortcut.key.toUpperCase()}
                  </kbd>
                </div>
              ))}
          </div>
          <div className="mt-4 pt-3 border-t border-void-600/50">
            <p className="text-2xs text-slate-500 text-center">
              Press <span className="text-cyan">?</span> to toggle
            </p>
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading && !lastUpdated ? (
          // Loading state
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="spinner mx-auto mb-4 w-8 h-8" />
              <p className="text-slate-400">Loading Control Plane...</p>
            </div>
          </div>
        ) : (
          // Dashboard grid
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* Left column: Agents + Directives */}
            <div className="xl:col-span-1 space-y-6">
              {/* Agents section */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Zap className="w-5 h-5 text-cyan" />
                  <h2 className="text-lg font-display font-semibold text-slate-100">
                    Active Agents
                  </h2>
                  <span className="text-xs text-slate-500">
                    ({agents.length})
                  </span>
                </div>
                <AgentStatusGrid
                  agents={agents}
                  onAgentClick={setSelectedAgent}
                />
              </section>

              {/* Directives section */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="w-5 h-5 text-warning" />
                  <h2 className="text-lg font-display font-semibold text-slate-100">
                    Directives
                  </h2>
                </div>
                <DirectivePanel
                  directiveState={directiveState}
                  onIssueHold={() => setIsHoldModalOpen(true)}
                  onGrantClearance={() => setIsClearanceModalOpen(true)}
                />
              </section>
            </div>

            {/* Center column: Operations Log */}
            <div className="xl:col-span-1">
              <section className="h-full flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Radio className="w-5 h-5 text-magenta" />
                  <h2 className="text-lg font-display font-semibold text-slate-100">
                    Operations Log
                  </h2>
                  <span className="text-xs text-slate-500">
                    ({opsLogEntries.length} events)
                  </span>
                  {wsConnected && (
                    <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-success">
                      <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                      Live
                    </span>
                  )}
                </div>
                <div className="flex-1 overflow-auto card p-2">
                  <OpsLogTimeline entries={opsLogEntries} maxEntries={30} />
                </div>
              </section>
            </div>

            {/* Right column: Tickets */}
            <div className="xl:col-span-1">
              <section className="h-full flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Radio className="w-5 h-5 text-cyan" />
                  <h2 className="text-lg font-display font-semibold text-slate-100">
                    Active Tickets
                  </h2>
                  <span className="text-xs text-slate-500">
                    ({activeTickets.length})
                  </span>
                </div>
                <div className="flex-1 overflow-auto">
                  <TicketsPanel
                    tickets={activeTickets}
                    onTicketClick={setSelectedTicket}
                  />
                </div>
              </section>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <HoldModal
        isOpen={isHoldModalOpen}
        onClose={() => setIsHoldModalOpen(false)}
        agents={agents}
        tickets={activeTickets}
        onSubmit={handleIssueHold}
      />

      <ClearanceModal
        isOpen={isClearanceModalOpen}
        onClose={() => setIsClearanceModalOpen(false)}
        agents={agents}
        tickets={activeTickets}
        onSubmit={handleGrantClearance}
      />

      <AgentDetailModal
        isOpen={selectedAgent !== null}
        onClose={() => setSelectedAgent(null)}
        agent={selectedAgent}
        recentActivity={opsLogEntries}
      />

      <TicketDetailModal
        isOpen={selectedTicket !== null}
        onClose={() => setSelectedTicket(null)}
        ticket={selectedTicket}
      />
    </div>
  )
}
