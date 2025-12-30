/**
 * Control Plane Zustand Store.
 *
 * Manages real-time state for the Control Plane dashboard.
 */

import { create } from 'zustand'
import type {
  AgentActivity,
  OpsLogEntry,
  TicketSummary,
  DirectiveState,
  DashboardMetrics,
  WSMessage,
} from '../types/controlPlane'

interface ControlPlaneState {
  // State
  agents: AgentActivity[]
  opsLogEntries: OpsLogEntry[]
  activeTickets: TicketSummary[]
  directiveState: DirectiveState
  metrics: DashboardMetrics
  lastUpdated: string | null
  isLoading: boolean
  error: string | null
  wsConnected: boolean

  // Actions
  setDashboardState: (data: {
    agents: AgentActivity[]
    ops_log_entries: OpsLogEntry[]
    active_tickets: TicketSummary[]
    directive_state: DirectiveState
    metrics: DashboardMetrics
    timestamp: string
  }) => void
  addOpsLogEntry: (entry: OpsLogEntry) => void
  updateAgent: (agent: AgentActivity) => void
  removeAgent: (agentName: string) => void
  updateTicket: (ticket: TicketSummary) => void
  updateDirectiveState: (directive: DirectiveState) => void
  setMetrics: (metrics: DashboardMetrics) => void
  setWSConnected: (connected: boolean) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  handleWSMessage: (message: WSMessage) => void
}

const initialDirectiveState: DirectiveState = {
  has_active_hold: false,
  has_active_clearance: false,
  latest_directive: null,
  affected_agents: [],
  affected_tickets: [],
}

const initialMetrics: DashboardMetrics = {
  active_agents: 0,
  agents_under_hold: 0,
  open_tickets: 0,
  in_progress_tickets: 0,
  under_review_tickets: 0,
  total_active_tickets: 0,
  today_activity_count: 0,
  websocket_connections: 0,
}

export const useControlPlaneStore = create<ControlPlaneState>((set, get) => ({
  // Initial state
  agents: [],
  opsLogEntries: [],
  activeTickets: [],
  directiveState: initialDirectiveState,
  metrics: initialMetrics,
  lastUpdated: null,
  isLoading: false,
  error: null,
  wsConnected: false,

  // Set full dashboard state (from REST API)
  setDashboardState: (data) =>
    set({
      agents: data.agents,
      opsLogEntries: data.ops_log_entries,
      activeTickets: data.active_tickets,
      directiveState: data.directive_state,
      metrics: data.metrics,
      lastUpdated: data.timestamp,
      isLoading: false,
      error: null,
    }),

  // Add a new ops log entry (prepend to list)
  addOpsLogEntry: (entry) =>
    set((state) => ({
      opsLogEntries: [entry, ...state.opsLogEntries].slice(0, 100), // Keep max 100
    })),

  // Update or add an agent
  updateAgent: (agent) =>
    set((state) => {
      const existing = state.agents.findIndex((a) => a.name === agent.name)
      if (existing >= 0) {
        const agents = [...state.agents]
        agents[existing] = agent
        return { agents }
      }
      return { agents: [...state.agents, agent] }
    }),

  // Remove an agent
  removeAgent: (agentName) =>
    set((state) => ({
      agents: state.agents.filter((a) => a.name !== agentName),
    })),

  // Update a ticket
  updateTicket: (ticket) =>
    set((state) => {
      const existing = state.activeTickets.findIndex((t) => t.id === ticket.id)
      if (existing >= 0) {
        const activeTickets = [...state.activeTickets]
        activeTickets[existing] = ticket
        return { activeTickets }
      }
      return { activeTickets: [...state.activeTickets, ticket] }
    }),

  // Update directive state
  updateDirectiveState: (directive) => set({ directiveState: directive }),

  // Set metrics
  setMetrics: (metrics) => set({ metrics }),

  // Set WebSocket connection status
  setWSConnected: (connected) => set({ wsConnected: connected }),

  // Set loading state
  setLoading: (loading) => set({ isLoading: loading }),

  // Set error
  setError: (error) => set({ error }),

  // Handle incoming WebSocket message
  handleWSMessage: (message) => {
    const { type, data } = message

    switch (type) {
      case 'ops_log:entry':
        get().addOpsLogEntry(data as unknown as OpsLogEntry)
        break

      case 'agent:started':
      case 'agent:status':
        // Convert ops log entry to agent activity
        const agentData = data as unknown as OpsLogEntry
        get().updateAgent({
          name: agentData.agent,
          is_active: true,
          last_seen: agentData.timestamp,
          current_ticket: agentData.ticket_id,
          last_action: agentData.event_type,
          activity_count: 1,
          has_clearance: false,
          under_hold: false,
        })
        get().addOpsLogEntry(agentData)
        break

      case 'agent:stopped':
        const stoppedAgent = data as unknown as OpsLogEntry
        get().removeAgent(stoppedAgent.agent)
        get().addOpsLogEntry(stoppedAgent)
        break

      case 'ticket:claimed':
      case 'ticket:completed':
      case 'ticket:updated':
        // Add to ops log
        get().addOpsLogEntry(data as unknown as OpsLogEntry)
        break

      case 'directive:hold':
        const holdEntry = data as unknown as OpsLogEntry
        set({
          directiveState: {
            has_active_hold: true,
            has_active_clearance: false,
            latest_directive: holdEntry,
            affected_agents: (holdEntry.metadata?.affected_agents as string[]) || [],
            affected_tickets: (holdEntry.metadata?.tickets as string[]) || [],
          },
        })
        get().addOpsLogEntry(holdEntry)
        break

      case 'directive:clearance':
        const clearanceEntry = data as unknown as OpsLogEntry
        set({
          directiveState: {
            has_active_hold: false,
            has_active_clearance: true,
            latest_directive: clearanceEntry,
            affected_agents: (clearanceEntry.metadata?.granted_to as string[]) || [],
            affected_tickets: (clearanceEntry.metadata?.tickets as string[]) || [],
          },
        })
        get().addOpsLogEntry(clearanceEntry)
        break

      default:
        console.log('[ControlPlane] Unhandled event type:', type)
    }
  },
}))

// Selectors
export const useActiveAgentCount = () =>
  useControlPlaneStore((state) => state.agents.filter((a) => a.is_active).length)

export const useAgentsUnderHold = () =>
  useControlPlaneStore((state) => state.agents.filter((a) => a.under_hold))

export const useRecentOpsLogEntries = (limit = 20) =>
  useControlPlaneStore((state) => state.opsLogEntries.slice(0, limit))

export const useOpenTickets = () =>
  useControlPlaneStore((state) => state.activeTickets.filter((t) => t.status === 'open'))

export const useInProgressTickets = () =>
  useControlPlaneStore((state) => state.activeTickets.filter((t) => t.status === 'in_progress'))
