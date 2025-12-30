/**
 * Agent Detail Modal - Shows detailed information about an agent.
 */

import { clsx } from 'clsx'
import {
  User,
  Clock,
  Ticket,
  Activity,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import { Modal } from './Modal'
import type { AgentActivity, OpsLogEntry } from '../../types/controlPlane'

interface AgentDetailModalProps {
  isOpen: boolean
  onClose: () => void
  agent: AgentActivity | null
  recentActivity: OpsLogEntry[]
}

export function AgentDetailModal({
  isOpen,
  onClose,
  agent,
  recentActivity,
}: AgentDetailModalProps) {
  if (!agent) return null

  const formatTime = (timestamp: string | null | undefined) => {
    if (!timestamp) return 'Unknown'
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getStatusColor = () => {
    if (agent.under_hold) return 'warning'
    if (agent.has_clearance) return 'success'
    if (agent.is_active) return 'cyan'
    return 'slate'
  }

  const getStatusText = () => {
    if (agent.under_hold) return 'Under Hold'
    if (agent.has_clearance) return 'Has Clearance'
    if (agent.is_active) return 'Active'
    return 'Inactive'
  }

  const getStatusIcon = () => {
    if (agent.under_hold) return <AlertTriangle className="w-5 h-5" />
    if (agent.has_clearance) return <Shield className="w-5 h-5" />
    if (agent.is_active) return <CheckCircle className="w-5 h-5" />
    return <XCircle className="w-5 h-5" />
  }

  // Filter activity for this agent
  const agentActivity = recentActivity
    .filter((entry) => entry.agent === agent.name)
    .slice(0, 10)

  const color = getStatusColor()

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Agent Details" size="lg">
      <div className="space-y-6">
        {/* Agent header */}
        <div className="flex items-start gap-4">
          <div
            className={clsx(
              'w-16 h-16 rounded-xl flex items-center justify-center',
              'bg-gradient-to-br',
              color === 'warning' && 'from-warning/20 to-warning/5 border border-warning/40',
              color === 'success' && 'from-success/20 to-success/5 border border-success/40',
              color === 'cyan' && 'from-cyan/20 to-cyan/5 border border-cyan/40',
              color === 'slate' && 'from-void-700 to-void-800 border border-void-600'
            )}
          >
            <User className={clsx('w-8 h-8', `text-${color}`)} />
          </div>

          <div className="flex-1">
            <h3 className="text-xl font-display font-semibold text-slate-100">
              {agent.name}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={clsx('text-sm', `text-${color}`)}>
                {getStatusIcon()}
              </span>
              <span className={clsx('text-sm font-medium', `text-${color}`)}>
                {getStatusText()}
              </span>
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-4">
          <div className="card p-4 text-center">
            <Clock className="w-5 h-5 text-slate-500 mx-auto mb-2" />
            <p className="text-xs text-slate-500 mb-1">Last Seen</p>
            <p className="text-sm text-slate-200">{formatTime(agent.last_seen)}</p>
          </div>

          <div className="card p-4 text-center">
            <Activity className="w-5 h-5 text-slate-500 mx-auto mb-2" />
            <p className="text-xs text-slate-500 mb-1">Activity Count</p>
            <p className="text-sm text-slate-200">{agent.activity_count}</p>
          </div>

          <div className="card p-4 text-center">
            <Ticket className="w-5 h-5 text-slate-500 mx-auto mb-2" />
            <p className="text-xs text-slate-500 mb-1">Current Ticket</p>
            <p className="text-sm text-slate-200">
              {agent.current_ticket ? `#${agent.current_ticket}` : 'None'}
            </p>
          </div>
        </div>

        {/* Last action */}
        {agent.last_action && (
          <div className="card p-4">
            <p className="text-xs text-slate-500 mb-1">Last Action</p>
            <p className="text-sm text-slate-200 font-mono">{agent.last_action}</p>
          </div>
        )}

        {/* Recent activity */}
        <div>
          <h4 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan" />
            Recent Activity
          </h4>

          {agentActivity.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No recent activity</p>
          ) : (
            <div className="space-y-2 max-h-48 overflow-auto">
              {agentActivity.map((entry, index) => (
                <div
                  key={entry.id || index}
                  className="flex items-start gap-3 p-2 rounded-lg bg-void-800/50"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan mt-2 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-300 truncate">
                      {entry.message}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatTime(entry.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}
