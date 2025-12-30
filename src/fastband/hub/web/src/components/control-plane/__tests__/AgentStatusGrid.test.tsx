/**
 * Tests for AgentStatusGrid Component.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '../../../test/utils'
import { AgentStatusGrid } from '../AgentStatusGrid'
import { createMockAgent } from '../../../test/utils'

describe('AgentStatusGrid', () => {
  it('renders empty state when no agents', () => {
    render(<AgentStatusGrid agents={[]} />)

    expect(screen.getByText('No Active Agents')).toBeInTheDocument()
    expect(
      screen.getByText('Agents will appear here when they connect')
    ).toBeInTheDocument()
  })

  it('renders all provided agents', () => {
    const agents = [
      createMockAgent({ name: 'Agent1' }),
      createMockAgent({ name: 'Agent2' }),
      createMockAgent({ name: 'Agent3' }),
    ]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Agent1')).toBeInTheDocument()
    expect(screen.getByText('Agent2')).toBeInTheDocument()
    expect(screen.getByText('Agent3')).toBeInTheDocument()
  })

  it('shows Active status for active agents', () => {
    const agents = [createMockAgent({ name: 'ActiveAgent', is_active: true })]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows Idle status for inactive agents', () => {
    const agents = [createMockAgent({ name: 'IdleAgent', is_active: false })]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Idle')).toBeInTheDocument()
  })

  it('shows Hold badge for agents under hold', () => {
    const agents = [createMockAgent({ name: 'HeldAgent', under_hold: true })]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Hold')).toBeInTheDocument()
  })

  it('shows Cleared badge for agents with clearance', () => {
    const agents = [
      createMockAgent({ name: 'ClearedAgent', has_clearance: true }),
    ]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Cleared')).toBeInTheDocument()
  })

  it('shows current ticket when agent is working on one', () => {
    const agents = [
      createMockAgent({ name: 'WorkingAgent', current_ticket: '1095' }),
    ]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Working on #1095')).toBeInTheDocument()
  })

  it('shows last action when available', () => {
    const agents = [
      createMockAgent({ name: 'RecentAgent', last_action: 'ticket:completed' }),
    ]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Last: ticket:completed')).toBeInTheDocument()
  })

  it('shows activity count', () => {
    const agents = [createMockAgent({ name: 'BusyAgent', activity_count: 42 })]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('42 actions')).toBeInTheDocument()
  })

  it('shows singular action for count of 1', () => {
    const agents = [createMockAgent({ name: 'NewAgent', activity_count: 1 })]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('1 action')).toBeInTheDocument()
  })

  it('calls onAgentClick when agent card is clicked', () => {
    const agents = [createMockAgent({ name: 'ClickableAgent' })]
    const handleClick = vi.fn()

    render(<AgentStatusGrid agents={agents} onAgentClick={handleClick} />)

    fireEvent.click(screen.getByText('ClickableAgent'))

    expect(handleClick).toHaveBeenCalledTimes(1)
    expect(handleClick).toHaveBeenCalledWith(agents[0])
  })

  it('shows relative time for last seen', () => {
    const now = new Date()
    const agents = [
      createMockAgent({
        name: 'RecentAgent',
        last_seen: now.toISOString(),
      }),
    ]

    render(<AgentStatusGrid agents={agents} />)

    expect(screen.getByText('Just now')).toBeInTheDocument()
  })
})
