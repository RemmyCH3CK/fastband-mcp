/**
 * Operations Log Timeline - Real-time activity feed.
 */

import { clsx } from 'clsx'
import {
  Bot,
  Play,
  Square,
  AlertTriangle,
  Shield,
  Ticket,
  CheckCircle,
  FileText,
  Clock
} from 'lucide-react'
import type { OpsLogEntry } from '../../types/controlPlane'

interface OpsLogTimelineProps {
  entries: OpsLogEntry[]
  maxEntries?: number
}

function getEventIcon(eventType: string) {
  const icons: Record<string, React.ReactNode> = {
    'agent:started': <Play className="w-4 h-4" />,
    'agent:stopped': <Square className="w-4 h-4" />,
    'ticket:claimed': <Ticket className="w-4 h-4" />,
    'ticket:completed': <CheckCircle className="w-4 h-4" />,
    'directive:hold': <AlertTriangle className="w-4 h-4" />,
    'directive:clearance': <Shield className="w-4 h-4" />,
    'status_update': <FileText className="w-4 h-4" />,
  }
  return icons[eventType] || <Bot className="w-4 h-4" />
}

function getEventColor(eventType: string) {
  if (eventType.includes('hold')) return 'warning'
  if (eventType.includes('clearance')) return 'success'
  if (eventType.includes('completed')) return 'success'
  if (eventType.includes('stopped')) return 'slate'
  if (eventType.includes('started') || eventType.includes('claimed')) return 'cyan'
  return 'slate'
}

function TimelineEntry({ entry, isFirst }: { entry: OpsLogEntry; isFirst: boolean }) {
  const color = getEventColor(entry.event_type)
  const icon = getEventIcon(entry.event_type)

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const colorClasses = {
    cyan: {
      icon: 'bg-cyan/20 border-cyan/40 text-cyan',
      line: 'bg-cyan/30',
      bg: 'hover:bg-cyan/5',
    },
    warning: {
      icon: 'bg-warning/20 border-warning/40 text-warning',
      line: 'bg-warning/30',
      bg: 'hover:bg-warning/5',
    },
    success: {
      icon: 'bg-success/20 border-success/40 text-success',
      line: 'bg-success/30',
      bg: 'hover:bg-success/5',
    },
    slate: {
      icon: 'bg-slate-700 border-slate-600 text-slate-400',
      line: 'bg-slate-700',
      bg: 'hover:bg-slate-800/50',
    },
  }

  const styles = colorClasses[color]

  return (
    <div className={clsx(
      'relative flex gap-4 py-3 px-4 rounded-lg transition-all duration-200',
      styles.bg,
      isFirst && 'animate-in bg-opacity-100',
      isFirst && color === 'cyan' && 'shadow-[0_0_20px_rgba(0,212,255,0.1)]',
      isFirst && color === 'warning' && 'shadow-[0_0_20px_rgba(245,158,11,0.1)]',
      isFirst && color === 'success' && 'shadow-[0_0_20px_rgba(16,185,129,0.1)]'
    )}>
      {/* Timeline connector with glow */}
      <div className="absolute left-[30px] top-[44px] bottom-0 w-0.5">
        <div className={clsx('h-full timeline-connector', styles.line)} />
      </div>

      {/* Icon with enhanced styling */}
      <div className={clsx(
        'relative z-10 w-8 h-8 rounded-lg border flex items-center justify-center flex-shrink-0',
        'transition-all duration-300',
        styles.icon,
        isFirst && 'scale-110'
      )}>
        {icon}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <span className="font-medium text-slate-200">{entry.agent}</span>
            {entry.ticket_id && (
              <span className="ml-2 text-magenta">
                #{entry.ticket_id}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 flex-shrink-0">
            <Clock className="w-3 h-3" />
            {formatTime(entry.timestamp)}
          </div>
        </div>

        <p className="text-sm text-slate-400 mt-0.5 truncate">
          {entry.message}
        </p>

        <div className="flex items-center gap-2 mt-1.5">
          <span className={clsx(
            'inline-flex items-center px-2 py-0.5 rounded text-xs font-mono',
            'bg-void-700 border border-void-600 text-slate-400'
          )}>
            {entry.event_type}
          </span>
        </div>
      </div>
    </div>
  )
}

export function OpsLogTimeline({ entries, maxEntries = 20 }: OpsLogTimelineProps) {
  const displayEntries = entries.slice(0, maxEntries)

  if (displayEntries.length === 0) {
    return (
      <div className="card p-8 text-center">
        <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <h3 className="text-lg font-medium text-slate-400">No Activity Yet</h3>
        <p className="text-sm text-slate-500 mt-1">
          Agent operations will appear here in real-time
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {displayEntries.map((entry, index) => (
        <TimelineEntry
          key={entry.id}
          entry={entry}
          isFirst={index === 0}
        />
      ))}
    </div>
  )
}
