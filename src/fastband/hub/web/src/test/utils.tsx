/**
 * Test Utilities for Control Plane Dashboard.
 */

import { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import type {
  AgentActivity,
  OpsLogEntry,
  TicketSummary,
  DirectiveState,
  DashboardMetrics,
} from '../types/controlPlane'

// Custom render function with providers
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { ...options })

export * from '@testing-library/react'
export { customRender as render }

// Factory functions for creating test data

export function createMockAgent(overrides: Partial<AgentActivity> = {}): AgentActivity {
  return {
    name: 'MCP_Agent1',
    is_active: true,
    last_seen: new Date().toISOString(),
    current_ticket: '1095',
    last_action: 'ticket:claimed',
    activity_count: 5,
    has_clearance: false,
    under_hold: false,
    ...overrides,
  }
}

export function createMockOpsLogEntry(overrides: Partial<OpsLogEntry> = {}): OpsLogEntry {
  return {
    id: `entry-${Date.now()}`,
    timestamp: new Date().toISOString(),
    agent: 'MCP_Agent1',
    event_type: 'ticket:claimed',
    message: 'Agent claimed ticket #1095',
    ticket_id: '1095',
    metadata: {},
    ttl_seconds: null,
    expires_at: null,
    ...overrides,
  }
}

export function createMockTicket(overrides: Partial<TicketSummary> = {}): TicketSummary {
  return {
    id: 'ticket-1095',
    ticket_number: '1095',
    title: 'Fix button alignment',
    status: 'in_progress',
    priority: 'high',
    assigned_to: 'MCP_Agent1',
    ticket_type: 'Bug',
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

export function createMockDirectiveState(
  overrides: Partial<DirectiveState> = {}
): DirectiveState {
  return {
    has_active_hold: false,
    has_active_clearance: false,
    latest_directive: null,
    affected_agents: [],
    affected_tickets: [],
    ...overrides,
  }
}

export function createMockMetrics(overrides: Partial<DashboardMetrics> = {}): DashboardMetrics {
  return {
    active_agents: 2,
    agents_under_hold: 0,
    open_tickets: 5,
    in_progress_tickets: 3,
    under_review_tickets: 2,
    total_active_tickets: 10,
    today_activity_count: 25,
    websocket_connections: 1,
    ...overrides,
  }
}
