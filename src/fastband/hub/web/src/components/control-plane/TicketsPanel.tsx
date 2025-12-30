/**
 * Tickets Panel - Shows active tickets in the system.
 */

import { clsx } from 'clsx'
import { Ticket, Circle, User, ChevronRight } from 'lucide-react'
import type { TicketSummary } from '../../types/controlPlane'

interface TicketsPanelProps {
  tickets: TicketSummary[]
  onTicketClick?: (ticket: TicketSummary) => void
}

function getStatusColor(status: string) {
  const normalizedStatus = status.toLowerCase().replace(/[^a-z_]/g, '')
  if (normalizedStatus.includes('open')) return 'cyan'
  if (normalizedStatus.includes('progress')) return 'magenta'
  if (normalizedStatus.includes('review')) return 'warning'
  if (normalizedStatus.includes('resolved') || normalizedStatus.includes('closed'))
    return 'success'
  return 'slate'
}

function getPriorityColor(priority: string) {
  const normalizedPriority = priority.toLowerCase()
  if (normalizedPriority === 'critical') return 'error'
  if (normalizedPriority === 'high') return 'warning'
  if (normalizedPriority === 'medium') return 'cyan'
  return 'slate'
}

function TicketRow({
  ticket,
  onClick,
}: {
  ticket: TicketSummary
  onClick?: () => void
}) {
  const statusColor = getStatusColor(ticket.status)
  const priorityColor = getPriorityColor(ticket.priority)

  const statusColorClasses = {
    cyan: 'text-cyan bg-cyan/10 border-cyan/30',
    magenta: 'text-magenta bg-magenta/10 border-magenta/30',
    warning: 'text-warning bg-warning/10 border-warning/30',
    success: 'text-success bg-success/10 border-success/30',
    slate: 'text-slate-400 bg-slate-700 border-slate-600',
  }

  const priorityColorClasses = {
    error: 'text-error',
    warning: 'text-warning',
    cyan: 'text-cyan',
    slate: 'text-slate-400',
  }

  // Clean up status display
  const cleanStatus = ticket.status.replace(/[^a-zA-Z\s]/g, '').trim()

  return (
    <div
      onClick={onClick}
      className={clsx(
        'flex items-center gap-4 px-4 py-3 rounded-lg',
        'bg-void-800/50 border border-void-600/30',
        'hover:bg-void-700/50 hover:border-void-500/50',
        'transition-all duration-200 cursor-pointer group'
      )}
    >
      {/* Ticket icon with status indicator */}
      <div className="relative">
        <Ticket
          className={clsx(
            'w-5 h-5',
            statusColor === 'magenta' ? 'text-magenta' : 'text-slate-500'
          )}
        />
        <Circle
          className={clsx(
            'absolute -top-0.5 -right-0.5 w-2.5 h-2.5 fill-current',
            statusColor === 'cyan' && 'text-cyan',
            statusColor === 'magenta' && 'text-magenta',
            statusColor === 'warning' && 'text-warning',
            statusColor === 'success' && 'text-success',
            statusColor === 'slate' && 'text-slate-500'
          )}
        />
      </div>

      {/* Ticket info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-magenta">
            #{ticket.ticket_number}
          </span>
          <span
            className={clsx(
              'w-1.5 h-1.5 rounded-full',
              priorityColorClasses[priorityColor]
            )}
            title={`Priority: ${ticket.priority}`}
          />
        </div>
        <h4 className="text-sm text-slate-200 truncate mt-0.5">{ticket.title}</h4>
      </div>

      {/* Status badge */}
      <span
        className={clsx(
          'hidden sm:inline-flex px-2 py-0.5 rounded text-xs border',
          statusColorClasses[statusColor]
        )}
      >
        {cleanStatus}
      </span>

      {/* Assigned to */}
      {ticket.assigned_to && (
        <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-500">
          <User className="w-3.5 h-3.5" />
          <span className="truncate max-w-[100px]">{ticket.assigned_to}</span>
        </div>
      )}

      {/* Type badge */}
      <span className="hidden lg:inline-block px-2 py-0.5 rounded text-xs bg-void-700 text-slate-400 border border-void-600">
        {ticket.ticket_type}
      </span>

      {/* Chevron */}
      <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
    </div>
  )
}

export function TicketsPanel({ tickets, onTicketClick }: TicketsPanelProps) {
  // Group tickets by status
  const inProgress = tickets.filter((t) =>
    t.status.toLowerCase().includes('progress')
  )
  const underReview = tickets.filter((t) =>
    t.status.toLowerCase().includes('review')
  )
  const open = tickets.filter((t) => t.status.toLowerCase().includes('open'))
  const other = tickets.filter(
    (t) =>
      !t.status.toLowerCase().includes('progress') &&
      !t.status.toLowerCase().includes('review') &&
      !t.status.toLowerCase().includes('open')
  )

  const groups = [
    { label: 'In Progress', tickets: inProgress, color: 'magenta' },
    { label: 'Under Review', tickets: underReview, color: 'warning' },
    { label: 'Open', tickets: open, color: 'cyan' },
    { label: 'Other', tickets: other, color: 'slate' },
  ].filter((g) => g.tickets.length > 0)

  if (tickets.length === 0) {
    return (
      <div className="card p-8 text-center">
        <Ticket className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <h3 className="text-lg font-medium text-slate-400">No Active Tickets</h3>
        <p className="text-sm text-slate-500 mt-1">
          Active tickets will appear here
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <div key={group.label}>
          <div className="flex items-center gap-2 mb-3">
            <h3
              className={clsx(
                'text-sm font-medium uppercase tracking-wider',
                group.color === 'magenta' && 'text-magenta',
                group.color === 'warning' && 'text-warning',
                group.color === 'cyan' && 'text-cyan',
                group.color === 'slate' && 'text-slate-400'
              )}
            >
              {group.label}
            </h3>
            <span className="text-xs text-slate-500">({group.tickets.length})</span>
          </div>
          <div className="space-y-2">
            {group.tickets.map((ticket) => (
              <TicketRow
                key={ticket.id}
                ticket={ticket}
                onClick={onTicketClick ? () => onTicketClick(ticket) : undefined}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
