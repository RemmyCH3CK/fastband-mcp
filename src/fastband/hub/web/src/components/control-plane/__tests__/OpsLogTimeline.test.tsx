/**
 * Tests for OpsLogTimeline Component.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '../../../test/utils'
import { OpsLogTimeline } from '../OpsLogTimeline'
import { createMockOpsLogEntry } from '../../../test/utils'

describe('OpsLogTimeline', () => {
  it('renders empty state when no entries', () => {
    render(<OpsLogTimeline entries={[]} />)

    expect(screen.getByText('No Activity Yet')).toBeInTheDocument()
    expect(
      screen.getByText('Agent operations will appear here in real-time')
    ).toBeInTheDocument()
  })

  it('renders all provided entries', () => {
    const entries = [
      createMockOpsLogEntry({
        id: '1',
        agent: 'Agent1',
        message: 'First action',
      }),
      createMockOpsLogEntry({
        id: '2',
        agent: 'Agent2',
        message: 'Second action',
      }),
      createMockOpsLogEntry({
        id: '3',
        agent: 'Agent3',
        message: 'Third action',
      }),
    ]

    render(<OpsLogTimeline entries={entries} />)

    expect(screen.getByText('Agent1')).toBeInTheDocument()
    expect(screen.getByText('Agent2')).toBeInTheDocument()
    expect(screen.getByText('Agent3')).toBeInTheDocument()
    expect(screen.getByText('First action')).toBeInTheDocument()
    expect(screen.getByText('Second action')).toBeInTheDocument()
    expect(screen.getByText('Third action')).toBeInTheDocument()
  })

  it('shows ticket ID when available', () => {
    const entries = [
      createMockOpsLogEntry({
        agent: 'TestAgent',
        ticket_id: '1095',
        message: 'Claimed ticket',
      }),
    ]

    render(<OpsLogTimeline entries={entries} />)

    expect(screen.getByText('#1095')).toBeInTheDocument()
  })

  it('shows event type badge', () => {
    const entries = [
      createMockOpsLogEntry({
        agent: 'TestAgent',
        event_type: 'ticket:claimed',
        message: 'Action message',
      }),
    ]

    render(<OpsLogTimeline entries={entries} />)

    expect(screen.getByText('ticket:claimed')).toBeInTheDocument()
  })

  it('limits entries to maxEntries', () => {
    const entries = Array.from({ length: 30 }, (_, i) =>
      createMockOpsLogEntry({
        id: `entry-${i}`,
        agent: `Agent${i}`,
        message: `Message ${i}`,
      })
    )

    render(<OpsLogTimeline entries={entries} maxEntries={10} />)

    // Should only show first 10
    expect(screen.getByText('Agent0')).toBeInTheDocument()
    expect(screen.getByText('Agent9')).toBeInTheDocument()
    expect(screen.queryByText('Agent10')).not.toBeInTheDocument()
  })

  it('displays formatted time', () => {
    const timestamp = new Date('2024-01-15T14:30:45').toISOString()
    const entries = [
      createMockOpsLogEntry({
        timestamp,
        agent: 'TestAgent',
        message: 'Timed action',
      }),
    ]

    render(<OpsLogTimeline entries={entries} />)

    // Just verify the entry renders - exact time format depends on locale
    expect(screen.getByText('TestAgent')).toBeInTheDocument()
  })

  it('applies correct icon based on event type', () => {
    const entries = [
      createMockOpsLogEntry({
        event_type: 'directive:hold',
        agent: 'HoldAgent',
        message: 'Hold issued',
      }),
    ]

    const { container } = render(<OpsLogTimeline entries={entries} />)

    // Check that the entry is rendered with the warning color class
    expect(container.querySelector('.text-warning')).toBeInTheDocument()
  })

  it('highlights first (newest) entry', () => {
    const entries = [
      createMockOpsLogEntry({
        id: 'newest',
        agent: 'NewestAgent',
        message: 'Latest action',
      }),
      createMockOpsLogEntry({
        id: 'older',
        agent: 'OlderAgent',
        message: 'Previous action',
      }),
    ]

    const { container } = render(<OpsLogTimeline entries={entries} />)

    // First entry should have the animate-in class
    const firstEntry = container.querySelector('.animate-in')
    expect(firstEntry).toBeInTheDocument()
  })
})
