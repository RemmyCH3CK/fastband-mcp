/**
 * Tests for Control Plane Zustand Store.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useControlPlaneStore } from './controlPlane'
import {
  createMockAgent,
  createMockOpsLogEntry,
  createMockTicket,
  createMockDirectiveState,
  createMockMetrics,
} from '../test/utils'

describe('Control Plane Store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useControlPlaneStore.setState({
      agents: [],
      opsLogEntries: [],
      activeTickets: [],
      directiveState: {
        has_active_hold: false,
        has_active_clearance: false,
        latest_directive: null,
        affected_agents: [],
        affected_tickets: [],
      },
      metrics: {
        active_agents: 0,
        agents_under_hold: 0,
        open_tickets: 0,
        in_progress_tickets: 0,
        under_review_tickets: 0,
        total_active_tickets: 0,
        today_activity_count: 0,
        websocket_connections: 0,
      },
      lastUpdated: null,
      isLoading: false,
      error: null,
      wsConnected: false,
    })
  })

  describe('setDashboardState', () => {
    it('sets full dashboard state from API response', () => {
      const agents = [createMockAgent()]
      const opsLogEntries = [createMockOpsLogEntry()]
      const activeTickets = [createMockTicket()]
      const directiveState = createMockDirectiveState()
      const metrics = createMockMetrics()
      const timestamp = new Date().toISOString()

      act(() => {
        useControlPlaneStore.getState().setDashboardState({
          agents,
          ops_log_entries: opsLogEntries,
          active_tickets: activeTickets,
          directive_state: directiveState,
          metrics,
          timestamp,
        })
      })

      const state = useControlPlaneStore.getState()
      expect(state.agents).toEqual(agents)
      expect(state.opsLogEntries).toEqual(opsLogEntries)
      expect(state.activeTickets).toEqual(activeTickets)
      expect(state.directiveState).toEqual(directiveState)
      expect(state.metrics).toEqual(metrics)
      expect(state.lastUpdated).toBe(timestamp)
      expect(state.isLoading).toBe(false)
      expect(state.error).toBeNull()
    })
  })

  describe('addOpsLogEntry', () => {
    it('adds entry to the beginning of the list', () => {
      const entry1 = createMockOpsLogEntry({ id: 'entry-1' })
      const entry2 = createMockOpsLogEntry({ id: 'entry-2' })

      act(() => {
        useControlPlaneStore.getState().addOpsLogEntry(entry1)
        useControlPlaneStore.getState().addOpsLogEntry(entry2)
      })

      const entries = useControlPlaneStore.getState().opsLogEntries
      expect(entries[0].id).toBe('entry-2')
      expect(entries[1].id).toBe('entry-1')
    })

    it('limits entries to 100', () => {
      // Add 110 entries
      act(() => {
        for (let i = 0; i < 110; i++) {
          useControlPlaneStore
            .getState()
            .addOpsLogEntry(createMockOpsLogEntry({ id: `entry-${i}` }))
        }
      })

      const entries = useControlPlaneStore.getState().opsLogEntries
      expect(entries.length).toBe(100)
      expect(entries[0].id).toBe('entry-109') // Most recent
    })
  })

  describe('updateAgent', () => {
    it('adds new agent if not exists', () => {
      const agent = createMockAgent({ name: 'NewAgent' })

      act(() => {
        useControlPlaneStore.getState().updateAgent(agent)
      })

      const agents = useControlPlaneStore.getState().agents
      expect(agents).toHaveLength(1)
      expect(agents[0].name).toBe('NewAgent')
    })

    it('updates existing agent', () => {
      const agent = createMockAgent({ name: 'TestAgent', activity_count: 1 })

      act(() => {
        useControlPlaneStore.getState().updateAgent(agent)
        useControlPlaneStore
          .getState()
          .updateAgent({ ...agent, activity_count: 5, current_ticket: '1100' })
      })

      const agents = useControlPlaneStore.getState().agents
      expect(agents).toHaveLength(1)
      expect(agents[0].activity_count).toBe(5)
      expect(agents[0].current_ticket).toBe('1100')
    })
  })

  describe('removeAgent', () => {
    it('removes agent by name', () => {
      const agent1 = createMockAgent({ name: 'Agent1' })
      const agent2 = createMockAgent({ name: 'Agent2' })

      act(() => {
        useControlPlaneStore.getState().updateAgent(agent1)
        useControlPlaneStore.getState().updateAgent(agent2)
        useControlPlaneStore.getState().removeAgent('Agent1')
      })

      const agents = useControlPlaneStore.getState().agents
      expect(agents).toHaveLength(1)
      expect(agents[0].name).toBe('Agent2')
    })

    it('does nothing if agent not found', () => {
      const agent = createMockAgent({ name: 'ExistingAgent' })

      act(() => {
        useControlPlaneStore.getState().updateAgent(agent)
        useControlPlaneStore.getState().removeAgent('NonExistent')
      })

      const agents = useControlPlaneStore.getState().agents
      expect(agents).toHaveLength(1)
    })
  })

  describe('updateTicket', () => {
    it('adds new ticket if not exists', () => {
      const ticket = createMockTicket({ id: 'ticket-new' })

      act(() => {
        useControlPlaneStore.getState().updateTicket(ticket)
      })

      const tickets = useControlPlaneStore.getState().activeTickets
      expect(tickets).toHaveLength(1)
      expect(tickets[0].id).toBe('ticket-new')
    })

    it('updates existing ticket', () => {
      const ticket = createMockTicket({ id: 'ticket-1', status: 'open' })

      act(() => {
        useControlPlaneStore.getState().updateTicket(ticket)
        useControlPlaneStore
          .getState()
          .updateTicket({ ...ticket, status: 'in_progress' })
      })

      const tickets = useControlPlaneStore.getState().activeTickets
      expect(tickets).toHaveLength(1)
      expect(tickets[0].status).toBe('in_progress')
    })
  })

  describe('handleWSMessage', () => {
    it('handles ops_log:entry event', () => {
      const entry = createMockOpsLogEntry({ event_type: 'status_update' })

      act(() => {
        useControlPlaneStore.getState().handleWSMessage({
          type: 'ops_log:entry',
          timestamp: new Date().toISOString(),
          data: entry as unknown as Record<string, unknown>,
        })
      })

      const entries = useControlPlaneStore.getState().opsLogEntries
      expect(entries).toHaveLength(1)
    })

    it('handles agent:started event', () => {
      const entry = createMockOpsLogEntry({
        agent: 'NewAgent',
        event_type: 'agent:started',
      })

      act(() => {
        useControlPlaneStore.getState().handleWSMessage({
          type: 'agent:started',
          timestamp: new Date().toISOString(),
          data: entry as unknown as Record<string, unknown>,
        })
      })

      const state = useControlPlaneStore.getState()
      expect(state.agents).toHaveLength(1)
      expect(state.agents[0].name).toBe('NewAgent')
      expect(state.agents[0].is_active).toBe(true)
      expect(state.opsLogEntries).toHaveLength(1)
    })

    it('handles agent:stopped event', () => {
      const agent = createMockAgent({ name: 'StoppingAgent' })
      const entry = createMockOpsLogEntry({
        agent: 'StoppingAgent',
        event_type: 'agent:stopped',
      })

      act(() => {
        useControlPlaneStore.getState().updateAgent(agent)
        useControlPlaneStore.getState().handleWSMessage({
          type: 'agent:stopped',
          timestamp: new Date().toISOString(),
          data: entry as unknown as Record<string, unknown>,
        })
      })

      const state = useControlPlaneStore.getState()
      expect(state.agents).toHaveLength(0)
      expect(state.opsLogEntries).toHaveLength(1)
    })

    it('handles directive:hold event', () => {
      const entry = createMockOpsLogEntry({
        agent: 'MCP_Agent1',
        event_type: 'directive:hold',
        message: 'Hold issued',
        metadata: {
          affected_agents: ['MCP_Agent2', 'MCP_Agent3'],
          tickets: ['1095', '1096'],
        },
      })

      act(() => {
        useControlPlaneStore.getState().handleWSMessage({
          type: 'directive:hold',
          timestamp: new Date().toISOString(),
          data: entry as unknown as Record<string, unknown>,
        })
      })

      const state = useControlPlaneStore.getState()
      expect(state.directiveState.has_active_hold).toBe(true)
      expect(state.directiveState.has_active_clearance).toBe(false)
      expect(state.directiveState.affected_agents).toEqual([
        'MCP_Agent2',
        'MCP_Agent3',
      ])
      expect(state.directiveState.affected_tickets).toEqual(['1095', '1096'])
    })

    it('handles directive:clearance event', () => {
      const entry = createMockOpsLogEntry({
        agent: 'MCP_Agent1',
        event_type: 'directive:clearance',
        message: 'Clearance granted',
        metadata: {
          granted_to: ['MCP_Agent2'],
          tickets: ['1100'],
        },
      })

      act(() => {
        useControlPlaneStore.getState().handleWSMessage({
          type: 'directive:clearance',
          timestamp: new Date().toISOString(),
          data: entry as unknown as Record<string, unknown>,
        })
      })

      const state = useControlPlaneStore.getState()
      expect(state.directiveState.has_active_hold).toBe(false)
      expect(state.directiveState.has_active_clearance).toBe(true)
      expect(state.directiveState.affected_agents).toEqual(['MCP_Agent2'])
      expect(state.directiveState.affected_tickets).toEqual(['1100'])
    })
  })

  describe('state setters', () => {
    it('setWSConnected updates connection status', () => {
      act(() => {
        useControlPlaneStore.getState().setWSConnected(true)
      })
      expect(useControlPlaneStore.getState().wsConnected).toBe(true)

      act(() => {
        useControlPlaneStore.getState().setWSConnected(false)
      })
      expect(useControlPlaneStore.getState().wsConnected).toBe(false)
    })

    it('setLoading updates loading state', () => {
      act(() => {
        useControlPlaneStore.getState().setLoading(true)
      })
      expect(useControlPlaneStore.getState().isLoading).toBe(true)
    })

    it('setError updates error state', () => {
      act(() => {
        useControlPlaneStore.getState().setError('Connection failed')
      })
      expect(useControlPlaneStore.getState().error).toBe('Connection failed')
    })
  })
})
