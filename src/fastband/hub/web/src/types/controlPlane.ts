/**
 * Control Plane TypeScript types.
 */

// Agent types
export interface AgentActivity {
  name: string
  is_active: boolean
  last_seen: string | null
  current_ticket: string | null
  last_action: string | null
  activity_count: number
  has_clearance: boolean
  under_hold: boolean
}

// Operations log types
export interface OpsLogEntry {
  id: string
  timestamp: string
  agent: string
  event_type: string
  message: string
  ticket_id: string | null
  metadata: Record<string, unknown>
  ttl_seconds: number | null
  expires_at: string | null
}

// Ticket types
export interface TicketSummary {
  id: string
  ticket_number: string
  title: string
  status: string
  priority: string
  assigned_to: string | null
  ticket_type: string
  created_at: string | null
}

// Directive types
export interface DirectiveState {
  has_active_hold: boolean
  has_active_clearance: boolean
  latest_directive: OpsLogEntry | null
  affected_agents: string[]
  affected_tickets: string[]
}

// Dashboard types
export interface DashboardMetrics {
  active_agents: number
  agents_under_hold: number
  open_tickets: number
  in_progress_tickets: number
  under_review_tickets: number
  total_active_tickets: number
  today_activity_count: number
  websocket_connections: number
}

export interface ControlPlaneDashboard {
  agents: AgentActivity[]
  ops_log_entries: OpsLogEntry[]
  active_tickets: TicketSummary[]
  directive_state: DirectiveState
  metrics: DashboardMetrics
  timestamp: string
}

// WebSocket message types
export type WSEventType =
  | 'agent:started'
  | 'agent:stopped'
  | 'agent:status'
  | 'ops_log:entry'
  | 'ticket:claimed'
  | 'ticket:completed'
  | 'ticket:updated'
  | 'directive:hold'
  | 'directive:clearance'
  | 'system:connected'
  | 'system:ping'
  | 'system:pong'
  | 'system:error'

export interface WSMessage {
  type: WSEventType
  timestamp: string
  data: Record<string, unknown>
}

// Subscription types
export type SubscriptionType = 'all' | 'agents' | 'ops_log' | 'tickets' | 'directives'

// API request types
export interface HoldRequest {
  issuing_agent: string
  affected_agents: string[]
  tickets?: string[]
  reason: string
}

export interface ClearanceRequest {
  granting_agent: string
  granted_to: string[]
  tickets: string[]
  reason: string
}

export interface DirectiveResponse {
  success: boolean
  entry_id: string
  message: string
}
