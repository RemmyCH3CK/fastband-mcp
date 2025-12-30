/**
 * Ticket Detail Modal - Shows detailed information about a ticket.
 */

import { clsx } from 'clsx'
import {
  Ticket,
  User,
  Clock,
  Tag,
  AlertCircle,
  CheckCircle,
  Circle,
  ExternalLink,
} from 'lucide-react'
import { Modal } from './Modal'
import type { TicketSummary } from '../../types/controlPlane'

interface TicketDetailModalProps {
  isOpen: boolean
  onClose: () => void
  ticket: TicketSummary | null
}

export function TicketDetailModal({
  isOpen,
  onClose,
  ticket,
}: TicketDetailModalProps) {
  if (!ticket) return null

  const formatDate = (timestamp: string | null | undefined) => {
    if (!timestamp) return 'Unknown'
    const date = new Date(timestamp)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase()
    if (s.includes('open')) return 'cyan'
    if (s.includes('progress')) return 'magenta'
    if (s.includes('review')) return 'warning'
    if (s.includes('resolved') || s.includes('closed')) return 'success'
    return 'slate'
  }

  const getPriorityColor = (priority: string) => {
    const p = priority.toLowerCase()
    if (p === 'critical') return 'error'
    if (p === 'high') return 'warning'
    if (p === 'medium') return 'cyan'
    return 'slate'
  }

  const getStatusIcon = (status: string) => {
    const s = status.toLowerCase()
    if (s.includes('resolved') || s.includes('closed')) {
      return <CheckCircle className="w-4 h-4" />
    }
    if (s.includes('progress')) {
      return <Circle className="w-4 h-4 animate-pulse" />
    }
    if (s.includes('review')) {
      return <AlertCircle className="w-4 h-4" />
    }
    return <Circle className="w-4 h-4" />
  }

  const statusColor = getStatusColor(ticket.status)
  const priorityColor = getPriorityColor(ticket.priority)

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Ticket Details" size="lg">
      <div className="space-y-6">
        {/* Ticket header */}
        <div className="flex items-start gap-4">
          <div
            className={clsx(
              'w-14 h-14 rounded-xl flex items-center justify-center',
              'bg-gradient-to-br from-magenta/20 to-magenta/5',
              'border border-magenta/40'
            )}
          >
            <Ticket className="w-7 h-7 text-magenta" />
          </div>

          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-mono text-magenta">
                #{ticket.ticket_number}
              </span>
              <span
                className={clsx(
                  'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs',
                  `bg-${statusColor}/20 text-${statusColor} border border-${statusColor}/30`
                )}
              >
                {getStatusIcon(ticket.status)}
                {ticket.status}
              </span>
            </div>
            <h3 className="text-lg font-display font-semibold text-slate-100">
              {ticket.title}
            </h3>
          </div>
        </div>

        {/* Info grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="card p-4">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Tag className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Priority</span>
            </div>
            <span
              className={clsx(
                'inline-flex items-center px-3 py-1 rounded-lg text-sm font-medium',
                `bg-${priorityColor}/10 text-${priorityColor} border border-${priorityColor}/30`
              )}
            >
              {ticket.priority}
            </span>
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Tag className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Type</span>
            </div>
            <span className="text-sm text-slate-200 capitalize">
              {ticket.ticket_type}
            </span>
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <User className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Assigned To</span>
            </div>
            <span className="text-sm text-slate-200">
              {ticket.assigned_to || 'Unassigned'}
            </span>
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Clock className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider">Created</span>
            </div>
            <span className="text-sm text-slate-200">
              {formatDate(ticket.created_at)}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={() => {
              // Navigate to ticket manager
              window.open(`/tickets/${ticket.id}`, '_blank')
            }}
            className="btn-secondary flex items-center gap-2 py-2"
          >
            <ExternalLink className="w-4 h-4" />
            <span>Open in Ticket Manager</span>
          </button>
        </div>
      </div>
    </Modal>
  )
}
