import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  Ticket,
  Plus,
  Trash2,
  Edit3,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Filter,
  X,
  Play,
  User,
  Clock,
  Tag,
} from 'lucide-react'
import { Layout } from '../components/Layout'

interface TicketData {
  id: string
  ticket_number: string | null
  title: string
  description: string
  ticket_type: string
  priority: string
  status: string
  assigned_to: string | null
  created_by: string
  created_at: string
  updated_at: string
  labels: string[]
  requirements: string[]
  notes: string
  resolution: string
}

interface TicketStats {
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  by_type: Record<string, number>
}

const STATUSES = ['open', 'in_progress', 'under_review', 'awaiting_approval', 'resolved', 'closed', 'blocked']
const PRIORITIES = ['critical', 'high', 'medium', 'low']
const TYPES = ['bug', 'feature', 'enhancement', 'task', 'documentation', 'maintenance', 'security', 'performance']

export function Tickets() {
  const [tickets, setTickets] = useState<TicketData[]>([])
  const [stats, setStats] = useState<TicketStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newTicket, setNewTicket] = useState({
    title: '',
    description: '',
    ticket_type: 'task',
    priority: 'medium',
    labels: '',
  })

  // Edit modal
  const [editingTicket, setEditingTicket] = useState<TicketData | null>(null)
  const [saving, setSaving] = useState(false)

  const fetchTickets = async () => {
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      if (priorityFilter) params.set('priority', priorityFilter)
      if (typeFilter) params.set('ticket_type', typeFilter)

      const response = await fetch(`/api/tickets?${params}`)
      if (response.ok) {
        const data = await response.json()
        setTickets(data)
      }
    } catch (err) {
      console.error('Failed to fetch tickets:', err)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/tickets/stats/summary')
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }

  const refresh = async () => {
    setLoading(true)
    await Promise.all([fetchTickets(), fetchStats()])
    setLoading(false)
  }

  useEffect(() => {
    refresh()
  }, [statusFilter, priorityFilter, typeFilter])

  const createTicket = async () => {
    if (!newTicket.title.trim()) {
      setError('Title is required')
      return
    }

    setCreating(true)
    setError(null)
    try {
      const response = await fetch('/api/tickets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newTicket,
          labels: newTicket.labels.split(',').map(l => l.trim()).filter(Boolean),
        }),
      })
      if (response.ok) {
        setSuccess('Ticket created successfully')
        setShowCreateModal(false)
        setNewTicket({ title: '', description: '', ticket_type: 'task', priority: 'medium', labels: '' })
        await refresh()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        const data = await response.json()
        setError(data.detail || 'Failed to create ticket')
      }
    } catch (err) {
      setError('Failed to create ticket')
    } finally {
      setCreating(false)
    }
  }

  const updateTicket = async () => {
    if (!editingTicket) return

    setSaving(true)
    setError(null)
    try {
      const response = await fetch(`/api/tickets/${editingTicket.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editingTicket.title,
          description: editingTicket.description,
          ticket_type: editingTicket.ticket_type,
          priority: editingTicket.priority,
          status: editingTicket.status,
          notes: editingTicket.notes,
        }),
      })
      if (response.ok) {
        setSuccess('Ticket updated')
        setEditingTicket(null)
        await refresh()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError('Failed to update ticket')
      }
    } catch (err) {
      setError('Failed to update ticket')
    } finally {
      setSaving(false)
    }
  }

  const deleteTicket = async (id: string) => {
    if (!confirm('Are you sure you want to delete this ticket?')) return
    try {
      const response = await fetch(`/api/tickets/${id}`, { method: 'DELETE' })
      if (response.ok) {
        setSuccess('Ticket deleted')
        await refresh()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError('Failed to delete ticket')
      }
    } catch (err) {
      setError('Failed to delete ticket')
    }
  }

  const claimTicket = async (id: string) => {
    try {
      const response = await fetch(`/api/tickets/${id}/claim`, { method: 'POST' })
      if (response.ok) {
        setSuccess('Ticket claimed')
        await refresh()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        const data = await response.json()
        setError(data.detail || 'Failed to claim ticket')
      }
    } catch (err) {
      setError('Failed to claim ticket')
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString()
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      open: 'bg-red-500/20 text-red-400',
      in_progress: 'bg-yellow-500/20 text-yellow-400',
      under_review: 'bg-blue-500/20 text-blue-400',
      awaiting_approval: 'bg-purple-500/20 text-purple-400',
      resolved: 'bg-green-500/20 text-green-400',
      closed: 'bg-gray-500/20 text-gray-400',
      blocked: 'bg-orange-500/20 text-orange-400',
    }
    return colors[status] || 'bg-gray-500/20 text-gray-400'
  }

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      critical: 'bg-red-500/20 text-red-400',
      high: 'bg-orange-500/20 text-orange-400',
      medium: 'bg-yellow-500/20 text-yellow-400',
      low: 'bg-green-500/20 text-green-400',
    }
    return colors[priority] || 'bg-gray-500/20 text-gray-400'
  }

  const getTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      bug: '🐛',
      feature: '✨',
      enhancement: '💡',
      task: '📋',
      documentation: '📚',
      maintenance: '🔧',
      security: '🔒',
      performance: '⚡',
    }
    return icons[type] || '📋'
  }

  return (
    <Layout showConversationSidebar={false}>
      <div className="h-full overflow-auto p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <Ticket className="w-6 h-6 text-cyan" />
                Ticket Manager
              </h1>
              <p className="text-slate-400 mt-1">
                Create, track, and manage development tickets
              </p>
            </div>
          <div className="flex items-center gap-3">
            <button
              onClick={refresh}
              disabled={loading}
              className="btn-icon"
              title="Refresh"
            >
              <RefreshCw className={clsx('w-5 h-5', loading && 'animate-spin')} />
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-cyan/20 text-cyan rounded-lg font-medium hover:bg-cyan/30 transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Ticket
            </button>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span className="text-red-400">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
              &times;
            </button>
          </div>
        )}
        {success && (
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="text-green-400">{success}</span>
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-void-800 rounded-xl border border-void-600/50 p-4">
              <div className="text-sm text-slate-400">Total Tickets</div>
              <div className="text-2xl font-bold text-white mt-1">{stats.total}</div>
            </div>
            <div className="bg-void-800 rounded-xl border border-void-600/50 p-4">
              <div className="text-sm text-slate-400">Open</div>
              <div className="text-2xl font-bold text-red-400 mt-1">{stats.by_status.open || 0}</div>
            </div>
            <div className="bg-void-800 rounded-xl border border-void-600/50 p-4">
              <div className="text-sm text-slate-400">In Progress</div>
              <div className="text-2xl font-bold text-yellow-400 mt-1">{stats.by_status.in_progress || 0}</div>
            </div>
            <div className="bg-void-800 rounded-xl border border-void-600/50 p-4">
              <div className="text-sm text-slate-400">Resolved</div>
              <div className="text-2xl font-bold text-green-400 mt-1">{stats.by_status.resolved || 0}</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-void-800 rounded-xl border border-void-600/50 p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-400">Filters:</span>
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-void-900 border border-void-600 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="">All Statuses</option>
              {STATUSES.map(s => (
                <option key={s} value={s}>{s.replace('_', ' ')}</option>
              ))}
            </select>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="bg-void-900 border border-void-600 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="">All Priorities</option>
              {PRIORITIES.map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-void-900 border border-void-600 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="">All Types</option>
              {TYPES.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            {(statusFilter || priorityFilter || typeFilter) && (
              <button
                onClick={() => { setStatusFilter(''); setPriorityFilter(''); setTypeFilter('') }}
                className="text-sm text-slate-400 hover:text-white"
              >
                Clear filters
              </button>
            )}
          </div>
        </div>

        {/* Tickets List */}
        <div className="bg-void-800 rounded-xl border border-void-600/50 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            Tickets ({tickets.length})
          </h2>

          {loading && tickets.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
              Loading tickets...
            </div>
          ) : tickets.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <Ticket className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No tickets found</p>
              <p className="text-sm mt-1">Create your first ticket above</p>
            </div>
          ) : (
            <div className="space-y-3">
              {tickets.map((ticket) => (
                <div
                  key={ticket.id}
                  className="bg-void-900/50 rounded-lg p-4"
                >
                  <div className="flex items-start gap-4">
                    <div className="text-2xl">{getTypeIcon(ticket.ticket_type)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 flex-wrap">
                        {ticket.ticket_number && (
                          <span className="text-sm text-slate-500 font-mono">
                            {ticket.ticket_number}
                          </span>
                        )}
                        <h3 className="text-white font-medium">{ticket.title}</h3>
                      </div>
                      <div className="flex items-center gap-3 mt-2 flex-wrap">
                        <span className={clsx(
                          'px-2 py-0.5 rounded text-xs font-medium',
                          getStatusColor(ticket.status)
                        )}>
                          {ticket.status.replace('_', ' ')}
                        </span>
                        <span className={clsx(
                          'px-2 py-0.5 rounded text-xs font-medium',
                          getPriorityColor(ticket.priority)
                        )}>
                          {ticket.priority}
                        </span>
                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(ticket.created_at)}
                        </span>
                        {ticket.assigned_to && (
                          <span className="text-xs text-slate-400 flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {ticket.assigned_to}
                          </span>
                        )}
                        {ticket.labels.length > 0 && (
                          <span className="text-xs text-slate-400 flex items-center gap-1">
                            <Tag className="w-3 h-3" />
                            {ticket.labels.join(', ')}
                          </span>
                        )}
                      </div>
                      {ticket.description && (
                        <p className="text-sm text-slate-400 mt-2 line-clamp-2">
                          {ticket.description}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {ticket.status === 'open' && (
                        <button
                          onClick={() => claimTicket(ticket.id)}
                          className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded-lg transition-colors"
                          title="Claim ticket"
                        >
                          <Play className="w-5 h-5" />
                        </button>
                      )}
                      <button
                        onClick={() => setEditingTicket(ticket)}
                        className="p-2 text-slate-400 hover:text-cyan hover:bg-cyan/10 rounded-lg transition-colors"
                        title="Edit ticket"
                      >
                        <Edit3 className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => deleteTicket(ticket.id)}
                        className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                        title="Delete ticket"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-void-800 rounded-xl border border-void-600/50 w-full max-w-lg">
            <div className="flex items-center justify-between p-4 border-b border-void-600/50">
              <h2 className="text-lg font-semibold text-white">Create New Ticket</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Title *</label>
                <input
                  type="text"
                  value={newTicket.title}
                  onChange={(e) => setNewTicket({ ...newTicket, title: e.target.value })}
                  className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  placeholder="Ticket title"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Description</label>
                <textarea
                  value={newTicket.description}
                  onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                  className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white h-24"
                  placeholder="Describe the ticket"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Type</label>
                  <select
                    value={newTicket.ticket_type}
                    onChange={(e) => setNewTicket({ ...newTicket, ticket_type: e.target.value })}
                    className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  >
                    {TYPES.map(t => (
                      <option key={t} value={t}>{getTypeIcon(t)} {t}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Priority</label>
                  <select
                    value={newTicket.priority}
                    onChange={(e) => setNewTicket({ ...newTicket, priority: e.target.value })}
                    className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  >
                    {PRIORITIES.map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Labels (comma-separated)</label>
                <input
                  type="text"
                  value={newTicket.labels}
                  onChange={(e) => setNewTicket({ ...newTicket, labels: e.target.value })}
                  className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  placeholder="frontend, urgent, v2"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-void-600/50">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={createTicket}
                disabled={creating}
                className="flex items-center gap-2 px-4 py-2 bg-cyan/20 text-cyan rounded-lg font-medium hover:bg-cyan/30 transition-colors disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Ticket'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingTicket && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-void-800 rounded-xl border border-void-600/50 w-full max-w-lg">
            <div className="flex items-center justify-between p-4 border-b border-void-600/50">
              <h2 className="text-lg font-semibold text-white">Edit Ticket</h2>
              <button onClick={() => setEditingTicket(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Title</label>
                <input
                  type="text"
                  value={editingTicket.title}
                  onChange={(e) => setEditingTicket({ ...editingTicket, title: e.target.value })}
                  className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Description</label>
                <textarea
                  value={editingTicket.description}
                  onChange={(e) => setEditingTicket({ ...editingTicket, description: e.target.value })}
                  className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white h-24"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Status</label>
                  <select
                    value={editingTicket.status}
                    onChange={(e) => setEditingTicket({ ...editingTicket, status: e.target.value })}
                    className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  >
                    {STATUSES.map(s => (
                      <option key={s} value={s}>{s.replace('_', ' ')}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Type</label>
                  <select
                    value={editingTicket.ticket_type}
                    onChange={(e) => setEditingTicket({ ...editingTicket, ticket_type: e.target.value })}
                    className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  >
                    {TYPES.map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Priority</label>
                  <select
                    value={editingTicket.priority}
                    onChange={(e) => setEditingTicket({ ...editingTicket, priority: e.target.value })}
                    className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white"
                  >
                    {PRIORITIES.map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Notes</label>
                <textarea
                  value={editingTicket.notes}
                  onChange={(e) => setEditingTicket({ ...editingTicket, notes: e.target.value })}
                  className="w-full bg-void-900 border border-void-600 rounded-lg px-3 py-2 text-white h-20"
                  placeholder="Additional notes..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-void-600/50">
              <button
                onClick={() => setEditingTicket(null)}
                className="px-4 py-2 text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={updateTicket}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-cyan/20 text-cyan rounded-lg font-medium hover:bg-cyan/30 transition-colors disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </Layout>
  )
}
