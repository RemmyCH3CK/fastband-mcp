/**
 * Tests for DirectivePanel Component.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '../../../test/utils'
import { DirectivePanel } from '../DirectivePanel'
import { createMockDirectiveState, createMockOpsLogEntry } from '../../../test/utils'

describe('DirectivePanel', () => {
  it('renders action buttons', () => {
    const directiveState = createMockDirectiveState()

    render(<DirectivePanel directiveState={directiveState} />)

    expect(screen.getByText('Issue Hold')).toBeInTheDocument()
    expect(screen.getByText('Grant Clearance')).toBeInTheDocument()
  })

  it('calls onIssueHold when Issue Hold button is clicked', () => {
    const directiveState = createMockDirectiveState()
    const handleHold = vi.fn()

    render(
      <DirectivePanel directiveState={directiveState} onIssueHold={handleHold} />
    )

    fireEvent.click(screen.getByText('Issue Hold'))

    expect(handleHold).toHaveBeenCalledTimes(1)
  })

  it('calls onGrantClearance when Grant Clearance button is clicked', () => {
    const directiveState = createMockDirectiveState()
    const handleClearance = vi.fn()

    render(
      <DirectivePanel
        directiveState={directiveState}
        onGrantClearance={handleClearance}
      />
    )

    fireEvent.click(screen.getByText('Grant Clearance'))

    expect(handleClearance).toHaveBeenCalledTimes(1)
  })

  it('shows inactive Hold card when no hold active', () => {
    const directiveState = createMockDirectiveState({ has_active_hold: false })

    render(<DirectivePanel directiveState={directiveState} />)

    expect(screen.getByText('Hold Active')).toBeInTheDocument()
    // Both cards show "No active directive" when inactive
    const inactiveTexts = screen.getAllByText('No active directive')
    expect(inactiveTexts.length).toBeGreaterThanOrEqual(1)
  })

  it('shows active Hold card with details when hold is active', () => {
    const entry = createMockOpsLogEntry({
      agent: 'MCP_Agent1',
      message: 'Major migration in progress',
    })

    const directiveState = createMockDirectiveState({
      has_active_hold: true,
      latest_directive: entry,
      affected_agents: ['MCP_Agent2', 'MCP_Agent3'],
      affected_tickets: ['1095', '1096'],
    })

    render(<DirectivePanel directiveState={directiveState} />)

    expect(screen.getByText('Currently in effect')).toBeInTheDocument()
    expect(screen.getByText('MCP_Agent1')).toBeInTheDocument()
    expect(screen.getByText('Major migration in progress')).toBeInTheDocument()
    expect(screen.getByText('MCP_Agent2')).toBeInTheDocument()
    expect(screen.getByText('MCP_Agent3')).toBeInTheDocument()
    expect(screen.getByText('#1095')).toBeInTheDocument()
    expect(screen.getByText('#1096')).toBeInTheDocument()
  })

  it('shows inactive Clearance card when no clearance active', () => {
    const directiveState = createMockDirectiveState({
      has_active_clearance: false,
    })

    render(<DirectivePanel directiveState={directiveState} />)

    expect(screen.getByText('Clearance Granted')).toBeInTheDocument()
    // Both cards show "No active directive" when inactive
    const inactiveTexts = screen.getAllByText('No active directive')
    expect(inactiveTexts.length).toBe(2)
  })

  it('shows active Clearance card with details when clearance is active', () => {
    const entry = createMockOpsLogEntry({
      agent: 'MCP_Agent1',
      message: 'Cleared for Phase 4 work',
    })

    const directiveState = createMockDirectiveState({
      has_active_clearance: true,
      latest_directive: entry,
      affected_agents: ['MCP_Agent2'],
      affected_tickets: ['1100'],
    })

    render(<DirectivePanel directiveState={directiveState} />)

    expect(screen.getByText('Currently in effect')).toBeInTheDocument()
    expect(screen.getByText('MCP_Agent1')).toBeInTheDocument()
    expect(screen.getByText('Cleared for Phase 4 work')).toBeInTheDocument()
    expect(screen.getByText('MCP_Agent2')).toBeInTheDocument()
    expect(screen.getByText('#1100')).toBeInTheDocument()
  })
})
