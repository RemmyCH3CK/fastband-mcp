import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  Archive,
  Plus,
  Trash2,
  RotateCcw,
  Play,
  Square,
  RefreshCw,
  Clock,
  HardDrive,
  FileText,
  AlertCircle,
  CheckCircle,
} from 'lucide-react'

interface Backup {
  id: string
  backup_type: string
  created_at: string
  size_bytes: number
  size_human: string
  files_count: number
  description: string
}

interface SchedulerStatus {
  running: boolean
  pid: number | null
  started_at: string | null
  last_backup_at: string | null
  next_backup_at: string | null
  backups_created: number
  errors: number
}

export function Backups() {
  const [backups, setBackups] = useState<Backup[]>([])
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const fetchBackups = async () => {
    try {
      const response = await fetch('/api/backups')
      if (response.ok) {
        const data = await response.json()
        setBackups(data)
      }
    } catch (err) {
      console.error('Failed to fetch backups:', err)
    }
  }

  const fetchSchedulerStatus = async () => {
    try {
      const response = await fetch('/api/backups/scheduler/status')
      if (response.ok) {
        const data = await response.json()
        setSchedulerStatus(data)
      }
    } catch (err) {
      console.error('Failed to fetch scheduler status:', err)
    }
  }

  const refresh = async () => {
    setLoading(true)
    await Promise.all([fetchBackups(), fetchSchedulerStatus()])
    setLoading(false)
  }

  useEffect(() => {
    refresh()
    // Refresh every 30 seconds
    const interval = setInterval(refresh, 30000)
    return () => clearInterval(interval)
  }, [])

  const createBackup = async () => {
    setCreating(true)
    setError(null)
    try {
      const response = await fetch('/api/backups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: description || 'Manual backup from dashboard',
          backup_type: 'manual',
        }),
      })
      if (response.ok) {
        setSuccess('Backup created successfully')
        setDescription('')
        await fetchBackups()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        const data = await response.json()
        setError(data.detail || 'Failed to create backup')
      }
    } catch (err) {
      setError('Failed to create backup')
    } finally {
      setCreating(false)
    }
  }

  const deleteBackup = async (id: string) => {
    if (!confirm('Are you sure you want to delete this backup?')) return
    try {
      const response = await fetch(`/api/backups/${id}`, { method: 'DELETE' })
      if (response.ok) {
        setSuccess('Backup deleted')
        await fetchBackups()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError('Failed to delete backup')
      }
    } catch (err) {
      setError('Failed to delete backup')
    }
  }

  const restoreBackup = async (id: string) => {
    if (!confirm('Are you sure you want to restore this backup? This will overwrite current files.')) return
    try {
      const response = await fetch(`/api/backups/${id}/restore`, { method: 'POST' })
      if (response.ok) {
        setSuccess('Backup restored successfully')
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError('Failed to restore backup')
      }
    } catch (err) {
      setError('Failed to restore backup')
    }
  }

  const toggleScheduler = async () => {
    const action = schedulerStatus?.running ? 'stop' : 'start'
    try {
      const response = await fetch(`/api/backups/scheduler/${action}`, { method: 'POST' })
      if (response.ok) {
        setSuccess(`Scheduler ${action}ed`)
        await fetchSchedulerStatus()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        setError(`Failed to ${action} scheduler`)
      }
    } catch (err) {
      setError(`Failed to ${action} scheduler`)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  const getBackupTypeColor = (type: string) => {
    switch (type) {
      case 'full':
        return 'bg-blue-500/20 text-blue-400'
      case 'incremental':
        return 'bg-purple-500/20 text-purple-400'
      case 'manual':
        return 'bg-green-500/20 text-green-400'
      default:
        return 'bg-gray-500/20 text-gray-400'
    }
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Archive className="w-6 h-6 text-cyan" />
              Backup Manager
            </h1>
            <p className="text-slate-400 mt-1">
              Create, restore, and manage project backups
            </p>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="btn-icon"
            title="Refresh"
          >
            <RefreshCw className={clsx('w-5 h-5', loading && 'animate-spin')} />
          </button>
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

        {/* Scheduler Status Card */}
        <div className="bg-void-800 rounded-xl border border-void-600/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Clock className="w-5 h-5 text-cyan" />
              Backup Scheduler
            </h2>
            <button
              onClick={toggleScheduler}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                schedulerStatus?.running
                  ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                  : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
              )}
            >
              {schedulerStatus?.running ? (
                <>
                  <Square className="w-4 h-4" />
                  Stop Scheduler
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Scheduler
                </>
              )}
            </button>
          </div>

          {schedulerStatus && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-void-900/50 rounded-lg p-4">
                <div className="text-sm text-slate-400">Status</div>
                <div className={clsx(
                  'text-lg font-semibold mt-1',
                  schedulerStatus.running ? 'text-green-400' : 'text-slate-500'
                )}>
                  {schedulerStatus.running ? 'Running' : 'Stopped'}
                </div>
              </div>
              <div className="bg-void-900/50 rounded-lg p-4">
                <div className="text-sm text-slate-400">Backups Created</div>
                <div className="text-lg font-semibold text-white mt-1">
                  {schedulerStatus.backups_created}
                </div>
              </div>
              <div className="bg-void-900/50 rounded-lg p-4">
                <div className="text-sm text-slate-400">Last Backup</div>
                <div className="text-sm text-white mt-1">
                  {schedulerStatus.last_backup_at
                    ? formatDate(schedulerStatus.last_backup_at)
                    : 'Never'}
                </div>
              </div>
              <div className="bg-void-900/50 rounded-lg p-4">
                <div className="text-sm text-slate-400">Next Backup</div>
                <div className="text-sm text-white mt-1">
                  {schedulerStatus.next_backup_at
                    ? formatDate(schedulerStatus.next_backup_at)
                    : 'Not scheduled'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Create Backup Card */}
        <div className="bg-void-800 rounded-xl border border-void-600/50 p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Plus className="w-5 h-5 text-cyan" />
            Create Backup
          </h2>
          <div className="flex gap-4">
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Backup description (optional)"
              className="flex-1 bg-void-900 border border-void-600 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan/50"
            />
            <button
              onClick={createBackup}
              disabled={creating}
              className="flex items-center gap-2 px-6 py-2 bg-cyan/20 text-cyan rounded-lg font-medium hover:bg-cyan/30 transition-colors disabled:opacity-50"
            >
              {creating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Create Backup
                </>
              )}
            </button>
          </div>
        </div>

        {/* Backups List */}
        <div className="bg-void-800 rounded-xl border border-void-600/50 p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <HardDrive className="w-5 h-5 text-cyan" />
            Backups ({backups.length})
          </h2>

          {loading && backups.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
              Loading backups...
            </div>
          ) : backups.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <Archive className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No backups yet</p>
              <p className="text-sm mt-1">Create your first backup above</p>
            </div>
          ) : (
            <div className="space-y-3">
              {backups.map((backup) => (
                <div
                  key={backup.id}
                  className="bg-void-900/50 rounded-lg p-4 flex items-center gap-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className={clsx(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        getBackupTypeColor(backup.backup_type)
                      )}>
                        {backup.backup_type}
                      </span>
                      <span className="text-sm text-slate-400">
                        {formatDate(backup.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm">
                      <span className="text-white flex items-center gap-1">
                        <HardDrive className="w-4 h-4 text-slate-400" />
                        {backup.size_human}
                      </span>
                      <span className="text-white flex items-center gap-1">
                        <FileText className="w-4 h-4 text-slate-400" />
                        {backup.files_count} files
                      </span>
                      {backup.description && (
                        <span className="text-slate-400 truncate">
                          {backup.description}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => restoreBackup(backup.id)}
                      className="p-2 text-slate-400 hover:text-cyan hover:bg-cyan/10 rounded-lg transition-colors"
                      title="Restore backup"
                    >
                      <RotateCcw className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => deleteBackup(backup.id)}
                      className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      title="Delete backup"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
