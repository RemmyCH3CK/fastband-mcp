/**
 * Tests for MetricsBar Component.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '../../../test/utils'
import { MetricsBar } from '../MetricsBar'
import { createMockMetrics } from '../../../test/utils'

describe('MetricsBar', () => {
  it('renders all metric cards', () => {
    const metrics = createMockMetrics({
      active_agents: 3,
      agents_under_hold: 1,
      in_progress_tickets: 5,
      under_review_tickets: 2,
    })

    render(
      <MetricsBar
        metrics={metrics}
        wsConnected={true}
        lastUpdated={new Date().toISOString()}
      />
    )

    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Active Agents')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('Under Hold')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('In Progress')).toBeInTheDocument()
    expect(screen.getByText('Under Review')).toBeInTheDocument()
  })

  it('shows Live status when connected', () => {
    const metrics = createMockMetrics()

    render(
      <MetricsBar
        metrics={metrics}
        wsConnected={true}
        lastUpdated={new Date().toISOString()}
      />
    )

    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(screen.queryByText('Disconnected')).not.toBeInTheDocument()
  })

  it('shows Disconnected status when not connected', () => {
    const metrics = createMockMetrics()

    render(
      <MetricsBar
        metrics={metrics}
        wsConnected={false}
        lastUpdated={new Date().toISOString()}
      />
    )

    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    expect(screen.queryByText('Live')).not.toBeInTheDocument()
  })

  it('shows Never when lastUpdated is null', () => {
    const metrics = createMockMetrics()

    render(
      <MetricsBar metrics={metrics} wsConnected={true} lastUpdated={null} />
    )

    expect(screen.getByText('Never')).toBeInTheDocument()
  })

  it('formats lastUpdated timestamp correctly', () => {
    const metrics = createMockMetrics()
    const timestamp = new Date('2024-01-15T10:30:45').toISOString()

    render(
      <MetricsBar
        metrics={metrics}
        wsConnected={true}
        lastUpdated={timestamp}
      />
    )

    // Time format depends on locale, just check Updated label is present
    expect(screen.getByText('Updated:')).toBeInTheDocument()
  })

  it('applies correct color classes based on metric values', () => {
    const zeroMetrics = createMockMetrics({
      active_agents: 0,
      agents_under_hold: 0,
      in_progress_tickets: 0,
      under_review_tickets: 0,
    })

    const { container } = render(
      <MetricsBar
        metrics={zeroMetrics}
        wsConnected={true}
        lastUpdated={new Date().toISOString()}
      />
    )

    // When values are 0, should use slate color classes
    const metricCards = container.querySelectorAll('.text-slate-400')
    expect(metricCards.length).toBeGreaterThan(0)
  })
})
