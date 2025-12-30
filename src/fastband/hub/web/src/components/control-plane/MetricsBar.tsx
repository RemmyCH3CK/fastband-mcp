/**
 * Metrics Bar - Top row of key metrics for the Control Plane.
 */

import { clsx } from 'clsx'
import { Activity, AlertTriangle, Ticket, Users, Radio, Clock } from 'lucide-react'
import type { DashboardMetrics } from '../../types/controlPlane'

interface MetricsBarProps {
  metrics: DashboardMetrics
  wsConnected: boolean
  lastUpdated: string | null
}

interface MetricCardProps {
  label: string
  value: number
  icon: React.ReactNode
  color: 'cyan' | 'magenta' | 'warning' | 'success' | 'slate'
  pulse?: boolean
}

function MetricCard({ label, value, icon, color, pulse }: MetricCardProps) {
  const colorClasses = {
    cyan: 'text-cyan border-cyan/30 bg-cyan/5',
    magenta: 'text-magenta border-magenta/30 bg-magenta/5',
    warning: 'text-warning border-warning/30 bg-warning/5',
    success: 'text-success border-success/30 bg-success/5',
    slate: 'text-slate-400 border-slate-600/30 bg-slate-800/30',
  }

  const glowClasses = {
    cyan: 'shadow-[0_0_30px_rgba(0,212,255,0.15)]',
    magenta: 'shadow-[0_0_30px_rgba(255,0,110,0.15)]',
    warning: 'shadow-[0_0_30px_rgba(245,158,11,0.15)]',
    success: 'shadow-[0_0_30px_rgba(16,185,129,0.15)]',
    slate: '',
  }

  return (
    <div
      className={clsx(
        'flex items-center gap-3 px-4 py-3 rounded-lg border',
        'transition-all duration-300 hover:scale-[1.02]',
        colorClasses[color],
        color !== 'slate' && glowClasses[color]
      )}
    >
      <div className={clsx('relative', pulse && 'status-pulse rounded-lg')}>
        {icon}
      </div>
      <div>
        <div className={clsx(
          'text-2xl font-display font-bold tabular-nums',
          color !== 'slate' && 'metric-value'
        )}>
          {value}
        </div>
        <div className="text-xs text-slate-400 uppercase tracking-wider">
          {label}
        </div>
      </div>
    </div>
  )
}

export function MetricsBar({ metrics, wsConnected, lastUpdated }: MetricsBarProps) {
  const formatTime = (timestamp: string | null) => {
    if (!timestamp) return 'Never'
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <div className="bg-void-800/50 border-b border-void-600/50 px-6 py-4">
      <div className="flex items-center justify-between gap-6">
        {/* Left: Key metrics */}
        <div className="flex items-center gap-4">
          <MetricCard
            label="Active Agents"
            value={metrics.active_agents}
            icon={<Users className="w-5 h-5" />}
            color={metrics.active_agents > 0 ? 'cyan' : 'slate'}
            pulse={metrics.active_agents > 0}
          />

          <MetricCard
            label="Under Hold"
            value={metrics.agents_under_hold}
            icon={<AlertTriangle className="w-5 h-5" />}
            color={metrics.agents_under_hold > 0 ? 'warning' : 'slate'}
          />

          <MetricCard
            label="In Progress"
            value={metrics.in_progress_tickets}
            icon={<Activity className="w-5 h-5" />}
            color={metrics.in_progress_tickets > 0 ? 'magenta' : 'slate'}
          />

          <MetricCard
            label="Under Review"
            value={metrics.under_review_tickets}
            icon={<Ticket className="w-5 h-5" />}
            color={metrics.under_review_tickets > 0 ? 'success' : 'slate'}
          />
        </div>

        {/* Right: Connection status */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-sm">
            <Clock className="w-4 h-4 text-slate-500" />
            <span className="text-slate-400">Updated:</span>
            <span className="text-slate-300 font-mono">{formatTime(lastUpdated)}</span>
          </div>

          <div className="flex items-center gap-2">
            <div className={clsx(
              'w-2 h-2 rounded-full',
              wsConnected ? 'bg-success animate-pulse' : 'bg-error'
            )} />
            <div className="flex items-center gap-1.5 text-sm">
              <Radio className={clsx(
                'w-4 h-4',
                wsConnected ? 'text-success' : 'text-error'
              )} />
              <span className={clsx(
                'font-medium',
                wsConnected ? 'text-success' : 'text-error'
              )}>
                {wsConnected ? 'Live' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
