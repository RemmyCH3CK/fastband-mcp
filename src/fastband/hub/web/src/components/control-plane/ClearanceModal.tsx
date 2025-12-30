/**
 * Clearance Modal - Grant clearance to agents for specific tickets.
 */

import { useState } from 'react'
import { clsx } from 'clsx'
import { Shield, Users, Ticket, Loader2, CheckCircle } from 'lucide-react'
import { Modal } from './Modal'
import type { AgentActivity, TicketSummary } from '../../types/controlPlane'

interface ClearanceModalProps {
  isOpen: boolean
  onClose: () => void
  agents: AgentActivity[]
  tickets: TicketSummary[]
  currentAgent?: string
  onSubmit: (data: {
    granting_agent: string
    granted_to: string[]
    tickets: string[]
    reason: string
  }) => Promise<void>
}

export function ClearanceModal({
  isOpen,
  onClose,
  agents,
  tickets,
  currentAgent = 'Human Operator',
  onSubmit,
}: ClearanceModalProps) {
  const [selectedAgents, setSelectedAgents] = useState<string[]>([])
  const [selectedTickets, setSelectedTickets] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Agents that could receive clearance
  const eligibleAgents = agents.filter((a) => a.is_active || a.under_hold)
  const activeTickets = tickets.filter(
    (t) =>
      t.status.toLowerCase().includes('progress') ||
      t.status.toLowerCase().includes('open') ||
      t.status.toLowerCase().includes('review')
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

  const handleSubmit = async () => {
    if (selectedAgents.length === 0) {
      setError('Please select at least one agent')
      return
    }
    if (selectedTickets.length === 0) {
      setError('Please select at least one ticket')
      return
    }
    if (!reason.trim()) {
      setError('Please provide a reason for the clearance')
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      await onSubmit({
        granting_agent: currentAgent,
        granted_to: selectedAgents,
        tickets: selectedTickets,
        reason: reason.trim(),
      })
      onClose()
      // Reset form
      setSelectedAgents([])
      setSelectedTickets([])
      setReason('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to grant clearance')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Grant Clearance"
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
            disabled={
              isSubmitting ||
              selectedAgents.length === 0 ||
              selectedTickets.length === 0
            }
            className={clsx(
              'px-6 py-2 font-medium rounded-lg',
              'bg-success text-void-900',
              'hover:bg-success/90',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors duration-200'
            )}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                Granting...
              </>
            ) : (
              <>
                <Shield className="w-4 h-4 inline mr-2" />
                Grant Clearance
              </>
            )}
          </button>
        </>
      }
    >
      <div className="space-y-6">
        {/* Info banner */}
        <div className="flex items-start gap-3 p-4 rounded-lg bg-success/10 border border-success/30">
          <CheckCircle className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
          <div className="text-sm text-slate-300">
            <p className="font-medium text-success">
              Authorize agents to work on specific tickets
            </p>
            <p className="mt-1 text-slate-400">
              This grants explicit permission and lifts any existing holds for
              the selected agents and tickets.
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
          <label className="flex items-center gap-2 text-sm font-medium text-slate-200 mb-3">
            <Users className="w-4 h-4 text-success" />
            Grant To
          </label>

          {eligibleAgents.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No agents available</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {eligibleAgents.map((agent) => (
                <button
                  key={agent.name}
                  onClick={() => toggleAgent(agent.name)}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-sm border transition-all',
                    selectedAgents.includes(agent.name)
                      ? 'bg-success/20 border-success/50 text-success'
                      : 'bg-void-700 border-void-600 text-slate-400 hover:border-success/30',
                    agent.under_hold && 'ring-1 ring-warning/50'
                  )}
                >
                  {agent.name}
                  {agent.under_hold && (
                    <span className="ml-1.5 text-warning text-xs">(held)</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Ticket selection (required) */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-200 mb-3">
            <Ticket className="w-4 h-4 text-magenta" />
            For Tickets
          </label>

          {activeTickets.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No active tickets</p>
          ) : (
            <div className="flex flex-wrap gap-2 max-h-40 overflow-auto">
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
                  title={ticket.title}
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
            Reason for Clearance
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain what work is authorized..."
            rows={3}
            className="input-field resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}
