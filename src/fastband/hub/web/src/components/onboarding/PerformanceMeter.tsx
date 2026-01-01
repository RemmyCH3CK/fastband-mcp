/**
 * Performance Meter Component
 *
 * Visual gradient meter showing tool selection impact on
 * system performance with dynamic recommendations.
 */

import { clsx } from 'clsx'
import { Cpu, HardDrive, Zap, AlertTriangle, CheckCircle, Activity } from 'lucide-react'

interface SystemInfo {
  ramGB: number
  cpuCores: number
  aiProvider: string
  contextWindow: number
}

interface PerformanceMeterProps {
  selectedCount: number
  maxRecommended: number
  systemInfo: SystemInfo
  className?: string
}

export function PerformanceMeter({
  selectedCount,
  maxRecommended,
  systemInfo,
  className,
}: PerformanceMeterProps) {
  // Calculate percentage and status
  const percentage = Math.min((selectedCount / maxRecommended) * 100, 100)
  const overflowPercentage = selectedCount > maxRecommended
    ? ((selectedCount - maxRecommended) / maxRecommended) * 100
    : 0

  const getStatus = () => {
    if (percentage <= 60) return { label: 'Optimal', color: 'cyan', icon: CheckCircle }
    if (percentage <= 80) return { label: 'Moderate', color: 'yellow', icon: Activity }
    return { label: 'Performance Impact', color: 'red', icon: AlertTriangle }
  }

  const status = getStatus()
  const StatusIcon = status.icon

  // Determine gradient colors based on position
  const getGradient = () => {
    if (percentage <= 60) {
      return 'from-emerald-500 via-cyan to-cyan'
    }
    if (percentage <= 80) {
      return 'from-emerald-500 via-cyan via-60% to-amber-500'
    }
    return 'from-emerald-500 via-cyan via-40% via-amber-500 via-70% to-red-500'
  }

  return (
    <div className={clsx('rounded-xl bg-void-800/50 border border-void-600/50 p-5', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-cyan" />
          <span className="text-sm font-medium text-slate-200">Performance Meter</span>
        </div>
        <div
          className={clsx(
            'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
            status.color === 'cyan' && 'bg-cyan/10 text-cyan border border-cyan/20',
            status.color === 'yellow' && 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
            status.color === 'red' && 'bg-red-500/10 text-red-400 border border-red-500/20',
          )}
        >
          <StatusIcon className="w-3 h-3" />
          {status.label}
        </div>
      </div>

      {/* Meter Bar */}
      <div className="relative h-3 bg-void-900 rounded-full overflow-hidden mb-3">
        {/* Background segments */}
        <div className="absolute inset-0 flex">
          <div className="w-[60%] border-r border-void-700/50" />
          <div className="w-[20%] border-r border-void-700/50" />
          <div className="w-[20%]" />
        </div>

        {/* Fill gradient */}
        <div
          className={clsx(
            'absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out',
            'bg-gradient-to-r',
            getGradient(),
          )}
          style={{
            width: `${Math.min(percentage, 100)}%`,
            boxShadow: `0 0 20px ${
              percentage <= 60 ? 'rgba(0, 212, 255, 0.5)' :
              percentage <= 80 ? 'rgba(245, 158, 11, 0.4)' :
              'rgba(239, 68, 68, 0.5)'
            }`,
          }}
        />

        {/* Overflow indicator */}
        {overflowPercentage > 0 && (
          <div
            className="absolute inset-y-0 right-0 bg-red-500/30 animate-pulse"
            style={{ width: `${Math.min(overflowPercentage, 50)}%` }}
          />
        )}

        {/* Current position marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-1 h-5 bg-white rounded-full shadow-lg transition-all duration-300"
          style={{
            left: `calc(${Math.min(percentage, 100)}% - 2px)`,
            boxShadow: '0 0 10px rgba(255, 255, 255, 0.8)',
          }}
        />
      </div>

      {/* Scale labels */}
      <div className="flex justify-between text-xs text-slate-500 mb-4">
        <span>0</span>
        <span className="text-cyan/60">Optimal</span>
        <span className="text-amber-500/60">Moderate</span>
        <span className="text-red-500/60">Heavy</span>
      </div>

      {/* Tool count */}
      <div className="flex items-center justify-between py-3 border-t border-void-600/30">
        <div>
          <span className="text-2xl font-display font-bold text-slate-100">{selectedCount}</span>
          <span className="text-slate-500 ml-1">/ {maxRecommended} tools</span>
        </div>
        {selectedCount > maxRecommended && (
          <div className="flex items-center gap-1.5 text-red-400 text-xs">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{selectedCount - maxRecommended} over limit</span>
          </div>
        )}
      </div>

      {/* System info */}
      <div className="grid grid-cols-2 gap-3 pt-3 border-t border-void-600/30">
        <div className="flex items-center gap-2 text-sm">
          <div className="w-7 h-7 rounded-lg bg-void-700 flex items-center justify-center">
            <HardDrive className="w-3.5 h-3.5 text-cyan/60" />
          </div>
          <div>
            <p className="text-slate-400 text-xs">RAM</p>
            <p className="text-slate-200 font-medium">{systemInfo.ramGB} GB</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-7 h-7 rounded-lg bg-void-700 flex items-center justify-center">
            <Cpu className="w-3.5 h-3.5 text-magenta/60" />
          </div>
          <div>
            <p className="text-slate-400 text-xs">Cores</p>
            <p className="text-slate-200 font-medium">{systemInfo.cpuCores}</p>
          </div>
        </div>
      </div>

      {/* Recommendation */}
      <div className="mt-4 p-3 rounded-lg bg-void-900/50 border border-void-700/50">
        <p className="text-xs text-slate-400">
          <span className="text-cyan">Recommendation:</span>{' '}
          Based on your system ({systemInfo.ramGB}GB RAM, {systemInfo.cpuCores} cores) and{' '}
          {systemInfo.aiProvider} ({(systemInfo.contextWindow / 1000).toFixed(0)}k context),
          we recommend up to <span className="text-slate-200 font-medium">{maxRecommended} tools</span> for optimal performance.
        </p>
      </div>
    </div>
  )
}
