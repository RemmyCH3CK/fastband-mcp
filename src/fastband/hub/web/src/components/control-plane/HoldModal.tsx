/**
 * Hold Modal - Issue a hold directive to pause agent work.
 */

import { useState } from 'react'
import { clsx } from 'clsx'
import { AlertTriangle, Users, Ticket, Loader2 } from 'lucide-react'
import { Modal } from './Modal'
import type { AgentActivity, TicketSummary } from '../../types/controlPlane'

interface HoldModalProps {
  isOpen: boolean
  onClose: () => void
  agents: AgentActivity[]
  tickets: TicketSummary[]
  currentAgent?: string
  onSubmit: (data: {
    issuing_agent: string
    affected_agents: string[]
    tickets: string[]
    reason: string
  }) => Promise<void>
}

export function HoldModal({
  isOpen,
  onClose,
  agents,
  tickets,
  currentAgent = 'Human Operator',
  onSubmit,
}: HoldModalProps) {
  const [selectedAgents, setSelectedAgents] = useState<string[]>([])
  const [selectedTickets, setSelectedTickets] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeAgents = agents.filter((a) => a.is_active)
  const activeTickets = tickets.filter(
    (t) =>
      t.status.toLowerCase().includes('progress') ||
      t.status.toLowerCase().includes('open')
  )

  const toggleAgent = (name: string) => {
    setSelectedAgents((prev) =>
      prev.includes(name)
        ? prev.filter((n) => n !== name)
        : [...prev, name]
    )
  }

  const toggleTicket = (id: string) => {
    setSelectedTickets((prev) =>
      prev.includes(id)
        ? prev.filter((i) => i !== id)
        : [...prev, id]
    )
  }

  const selectAllAgents = () => {
    setSelectedAgents(activeAgents.map((a) => a.name))
  }

  const handleSubmit = async () => {
    if (selectedAgents.length === 0) {
      setError('Please select at least one agent')
      return
    }
    if (!reason.trim()) {
      setError('Please provide a reason for the hold')
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      await onSubmit({
        issuing_agent: currentAgent,
        affected_agents: selectedAgents,
        tickets: selectedTickets,
        reason: reason.trim(),
      })
      onClose()
      // Reset form
      setSelectedAgents([])
      setSelectedTickets([])
      setReason('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to issue hold')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Issue Hold Directive"
      size="lg"
      footer={
        <>
          <button
            onClick={onClose}
            className="btn-secondary py-2"
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || selectedAgents.length === 0}
            className={clsx(
              'px-6 py-2 font-medium rounded-lg',
              'bg-warning text-void-900',
              'hover:bg-warning/90',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors duration-200'
            )}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                Issuing Hold...
              </>
            ) : (
              <>
                <AlertTriangle className="w-4 h-4 inline mr-2" />
                Issue Hold
              </>
            )}
          </button>
        </>
      }
    >
      <div className="space-y-6">
        {/* Warning banner */}
        <div className="flex items-start gap-3 p-4 rounded-lg bg-warning/10 border border-warning/30">
          <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
          <div className="text-sm text-slate-300">
            <p className="font-medium text-warning">This will pause agent work</p>
            <p className="mt-1 text-slate-400">
              Selected agents will be notified to stop their current work until
              the hold is lifted.
            </p>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-lg bg-error/10 border border-error/30 text-error text-sm">
            {error}
          </div>
        )}

        {/* Agent selection */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <Users className="w-4 h-4 text-warning" />
              Affected Agents
            </label>
            {activeAgents.length > 0 && (
              <button
                onClick={selectAllAgents}
                className="text-xs text-cyan hover:text-cyan-300"
              >
                Select All
              </button>
            )}
          </div>

          {activeAgents.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No active agents</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {activeAgents.map((agent) => (
                <button
                  key={agent.name}
                  onClick={() => toggleAgent(agent.name)}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-sm border transition-all',
                    selectedAgents.includes(agent.name)
                      ? 'bg-warning/20 border-warning/50 text-warning'
                      : 'bg-void-700 border-void-600 text-slate-400 hover:border-warning/30'
                  )}
                >
                  {agent.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Ticket selection (optional) */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-200 mb-3">
            <Ticket className="w-4 h-4 text-magenta" />
            Related Tickets (Optional)
          </label>

          {activeTickets.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No active tickets</p>
          ) : (
            <div className="flex flex-wrap gap-2 max-h-32 overflow-auto">
              {activeTickets.map((ticket) => (
                <button
                  key={ticket.id}
                  onClick={() => toggleTicket(ticket.ticket_number)}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-sm border transition-all',
                    selectedTickets.includes(ticket.ticket_number)
                      ? 'bg-magenta/20 border-magenta/50 text-magenta'
                      : 'bg-void-700 border-void-600 text-slate-400 hover:border-magenta/30'
                  )}
                >
                  #{ticket.ticket_number}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Reason */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-2">
            Reason for Hold
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why this hold is necessary..."
            rows={3}
            className="input-field resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}
