/**
 * Directive Panel - Shows current hold/clearance status.
 */

import { clsx } from 'clsx'
import { AlertTriangle, Shield, Clock, Users, Ticket } from 'lucide-react'
import type { DirectiveState, OpsLogEntry } from '../../types/controlPlane'

interface DirectivePanelProps {
  directiveState: DirectiveState
  onIssueHold?: () => void
  onGrantClearance?: () => void
}

function DirectiveCard({
  type,
  active,
  entry,
  affectedAgents,
  affectedTickets,
}: {
  type: 'hold' | 'clearance'
  active: boolean
  entry: OpsLogEntry | null
  affectedAgents: string[]
  affectedTickets: string[]
}) {
  const isHold = type === 'hold'

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div
      className={clsx(
        'relative rounded-xl border p-4 transition-all duration-300',
        active
          ? isHold
            ? 'border-warning/50 bg-warning/10 directive-active directive-hold'
            : 'border-success/50 bg-success/10 directive-active directive-clearance'
          : 'border-void-600/50 bg-void-800/30'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={clsx(
              'w-10 h-10 rounded-lg flex items-center justify-center',
              active
                ? isHold
                  ? 'bg-warning/20 border border-warning/40'
                  : 'bg-success/20 border border-success/40'
                : 'bg-void-700 border border-void-600'
            )}
          >
            {isHold ? (
              <AlertTriangle
                className={clsx(
                  'w-5 h-5',
                  active ? 'text-warning' : 'text-slate-500'
                )}
              />
            ) : (
              <Shield
                className={clsx(
                  'w-5 h-5',
                  active ? 'text-success' : 'text-slate-500'
                )}
              />
            )}
          </div>

          <div>
            <h3
              className={clsx(
                'font-display font-semibold',
                active
                  ? isHold
                    ? 'text-warning'
                    : 'text-success'
                  : 'text-slate-400'
              )}
            >
              {isHold ? 'Hold Active' : 'Clearance Granted'}
            </h3>
            <p className="text-sm text-slate-500">
              {active ? 'Currently in effect' : 'No active directive'}
            </p>
          </div>
        </div>

        {active && (
          <div
            className={clsx(
              'w-3 h-3 rounded-full animate-pulse',
              isHold ? 'bg-warning' : 'bg-success'
            )}
          />
        )}
      </div>

      {/* Details when active */}
      {active && entry && (
        <div className="mt-4 space-y-3 border-t border-void-600/50 pt-4">
          {/* Issued by and time */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">
              Issued by <span className="text-slate-200">{entry.agent}</span>
            </span>
            <div className="flex items-center gap-1.5 text-slate-500">
              <Clock className="w-3.5 h-3.5" />
              {formatTime(entry.timestamp)}
            </div>
          </div>

          {/* Reason */}
          <p className="text-sm text-slate-300">{entry.message}</p>

          {/* Affected agents */}
          {affectedAgents.length > 0 && (
            <div className="flex items-start gap-2 text-sm">
              <Users className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
              <div className="flex flex-wrap gap-1.5">
                {affectedAgents.map((agent) => (
                  <span
                    key={agent}
                    className={clsx(
                      'px-2 py-0.5 rounded text-xs',
                      isHold
                        ? 'bg-warning/20 text-warning border border-warning/30'
                        : 'bg-success/20 text-success border border-success/30'
                    )}
                  >
                    {agent}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Affected tickets */}
          {affectedTickets.length > 0 && (
            <div className="flex items-start gap-2 text-sm">
              <Ticket className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
              <div className="flex flex-wrap gap-1.5">
                {affectedTickets.map((ticketId) => (
                  <span
                    key={ticketId}
                    className="px-2 py-0.5 rounded text-xs bg-magenta/20 text-magenta border border-magenta/30"
                  >
                    #{ticketId}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function DirectivePanel({
  directiveState,
  onIssueHold,
  onGrantClearance,
}: DirectivePanelProps) {
  return (
    <div className="space-y-4">
      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={onIssueHold}
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
            'bg-warning/10 border border-warning/30 text-warning',
            'hover:bg-warning/20 hover:border-warning/50',
            'transition-all duration-200'
          )}
        >
          <AlertTriangle className="w-4 h-4" />
          <span className="font-medium text-sm">Issue Hold</span>
        </button>

        <button
          onClick={onGrantClearance}
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
            'bg-success/10 border border-success/30 text-success',
            'hover:bg-success/20 hover:border-success/50',
            'transition-all duration-200'
          )}
        >
          <Shield className="w-4 h-4" />
          <span className="font-medium text-sm">Grant Clearance</span>
        </button>
      </div>

      <DirectiveCard
        type="hold"
        active={directiveState.has_active_hold}
        entry={
          directiveState.has_active_hold ? directiveState.latest_directive : null
        }
        affectedAgents={
          directiveState.has_active_hold ? directiveState.affected_agents : []
        }
        affectedTickets={
          directiveState.has_active_hold ? directiveState.affected_tickets : []
        }
      />

      <DirectiveCard
        type="clearance"
        active={directiveState.has_active_clearance}
        entry={
          directiveState.has_active_clearance
            ? directiveState.latest_directive
            : null
        }
        affectedAgents={
          directiveState.has_active_clearance
            ? directiveState.affected_agents
            : []
        }
        affectedTickets={
          directiveState.has_active_clearance
            ? directiveState.affected_tickets
            : []
        }
      />
    </div>
  )
}
