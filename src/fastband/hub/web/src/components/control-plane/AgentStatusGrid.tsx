/**
 * Agent Status Grid - Shows active agents and their current status.
 */

import { clsx } from 'clsx'
import { Bot, Clock, Ticket, Shield, AlertOctagon, Circle } from 'lucide-react'
import type { AgentActivity } from '../../types/controlPlane'

interface AgentStatusGridProps {
  agents: AgentActivity[]
  onAgentClick?: (agent: AgentActivity) => void
}

function AgentCard({
  agent,
  onClick,
}: {
  agent: AgentActivity
  onClick?: () => void
}) {
  const formatTime = (timestamp: string | null) => {
    if (!timestamp) return 'Unknown'
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    return date.toLocaleDateString()
  }

  const getStatusColor = () => {
    if (agent.under_hold) return 'warning'
    if (agent.has_clearance) return 'success'
    if (agent.is_active) return 'cyan'
    return 'slate'
  }

  const statusColor = getStatusColor()
  const colorClasses = {
    cyan: 'border-cyan/40 bg-cyan/5',
    warning: 'border-warning/40 bg-warning/5',
    success: 'border-success/40 bg-success/5',
    slate: 'border-slate-600/40 bg-slate-800/30',
  }

  const glowClasses = {
    cyan: 'shadow-[0_0_25px_rgba(0,212,255,0.1)]',
    warning: 'shadow-[0_0_25px_rgba(245,158,11,0.15)]',
    success: 'shadow-[0_0_25px_rgba(16,185,129,0.1)]',
    slate: '',
  }

  return (
    <div
      onClick={onClick}
      className={clsx(
        'relative p-4 rounded-xl border',
        'transition-all duration-300 hover:scale-[1.02]',
        onClick && 'cursor-pointer',
        colorClasses[statusColor],
        agent.is_active && 'agent-active-indicator',
        statusColor !== 'slate' && glowClasses[statusColor]
      )}
    >
      {/* Status indicator */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        <Circle
          className={clsx(
            'w-2.5 h-2.5 fill-current',
            agent.is_active ? 'text-success' : 'text-slate-500'
          )}
        />
        <span className={clsx(
          'text-xs uppercase tracking-wider',
          agent.is_active ? 'text-success' : 'text-slate-500'
        )}>
          {agent.is_active ? 'Active' : 'Idle'}
        </span>
      </div>

      {/* Agent info */}
      <div className="flex items-start gap-3">
        <div className={clsx(
          'w-12 h-12 rounded-lg flex items-center justify-center',
          'bg-gradient-to-br',
          statusColor === 'warning'
            ? 'from-warning/20 to-warning/5 border border-warning/30'
            : statusColor === 'success'
            ? 'from-success/20 to-success/5 border border-success/30'
            : 'from-cyan/20 to-cyan/5 border border-cyan/30'
        )}>
          <Bot className={clsx(
            'w-6 h-6',
            statusColor === 'warning' ? 'text-warning' :
            statusColor === 'success' ? 'text-success' : 'text-cyan'
          )} />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-display font-semibold text-slate-100 truncate">
            {agent.name}
          </h3>

          {/* Status badges */}
          <div className="flex items-center gap-2 mt-1">
            {agent.under_hold && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-warning/20 text-warning border border-warning/30">
                <AlertOctagon className="w-3 h-3" />
                Hold
              </span>
            )}
            {agent.has_clearance && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-success/20 text-success border border-success/30">
                <Shield className="w-3 h-3" />
                Cleared
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="mt-4 space-y-2 text-sm">
        {agent.current_ticket && (
          <div className="flex items-center gap-2 text-slate-300">
            <Ticket className="w-4 h-4 text-magenta" />
            <span>Working on #{agent.current_ticket}</span>
          </div>
        )}

        {agent.last_action && (
          <div className="text-slate-400 truncate">
            Last: {agent.last_action}
          </div>
        )}

        <div className="flex items-center gap-2 text-slate-500">
          <Clock className="w-3.5 h-3.5" />
          <span className="text-xs">{formatTime(agent.last_seen)}</span>
        </div>
      </div>

      {/* Activity count */}
      <div className="absolute bottom-3 right-3 text-xs text-slate-500">
        {agent.activity_count} action{agent.activity_count !== 1 ? 's' : ''}
      </div>
    </div>
  )
}

export function AgentStatusGrid({ agents, onAgentClick }: AgentStatusGridProps) {
  if (agents.length === 0) {
    return (
      <div className="card p-8 text-center">
        <Bot className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <h3 className="text-lg font-medium text-slate-400">No Active Agents</h3>
        <p className="text-sm text-slate-500 mt-1">
          Agents will appear here when they connect
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {agents.map((agent) => (
        <AgentCard
          key={agent.name}
          agent={agent}
          onClick={onAgentClick ? () => onAgentClick(agent) : undefined}
        />
      ))}
    </div>
  )
}
