/**
 * Step 3: Feature Selection
 *
 * Toggle Backup system and Ticket Manager features.
 */

import { useEffect } from 'react'
import { clsx } from 'clsx'
import {
  HardDrive,
  Ticket,
  Clock,
  Shield,
  ListTodo,
  Users,
  History,
  Kanban,
} from 'lucide-react'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

export function FeaturesStep({ data, updateData, setStepValid }: StepProps) {
  // Always valid - features are optional
  useEffect(() => {
    setStepValid(true)
  }, [setStepValid])

  const features = [
    {
      id: 'backup',
      name: 'Backup System',
      icon: HardDrive,
      color: 'cyan',
      enabled: data.backupEnabled,
      toggle: () => updateData({ backupEnabled: !data.backupEnabled }),
      description: 'Automatic snapshots of your project state',
      benefits: [
        { icon: Clock, text: 'Scheduled backups every 2 hours' },
        { icon: Shield, text: 'Point-in-time recovery' },
        { icon: History, text: 'Version history with diffs' },
      ],
    },
    {
      id: 'tickets',
      name: 'Ticket Manager',
      icon: Ticket,
      color: 'magenta',
      enabled: data.ticketsEnabled,
      toggle: () => updateData({ ticketsEnabled: !data.ticketsEnabled }),
      description: 'Organize work with tickets and assignments',
      benefits: [
        { icon: ListTodo, text: 'Create and track tasks' },
        { icon: Users, text: 'Assign to AI agents' },
        { icon: Kanban, text: 'Visual ticket board' },
      ],
    },
  ]

  return (
    <div className="space-y-6 animate-in">
      <p className="text-sm text-slate-400">
        Enable or disable optional features. You can change these settings later.
      </p>

      {/* Feature toggles */}
      <div className="space-y-4">
        {features.map((feature) => {
          const Icon = feature.icon

          return (
            <div
              key={feature.id}
              className={clsx(
                'relative p-5 rounded-xl border transition-all duration-300',
                feature.enabled
                  ? feature.color === 'cyan'
                    ? 'bg-cyan/5 border-cyan/30'
                    : 'bg-magenta/5 border-magenta/30'
                  : 'bg-void-800/30 border-void-600/50',
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  {/* Icon */}
                  <div
                    className={clsx(
                      'w-12 h-12 rounded-xl flex items-center justify-center transition-colors duration-300',
                      feature.enabled
                        ? feature.color === 'cyan'
                          ? 'bg-cyan/20 text-cyan'
                          : 'bg-magenta/20 text-magenta'
                        : 'bg-void-700 text-slate-500',
                    )}
                  >
                    <Icon className="w-6 h-6" />
                  </div>

                  {/* Content */}
                  <div className="flex-1">
                    <h3 className="font-display font-semibold text-slate-100 mb-1">
                      {feature.name}
                    </h3>
                    <p className="text-sm text-slate-400 mb-3">
                      {feature.description}
                    </p>

                    {/* Benefits */}
                    <div
                      className={clsx(
                        'grid grid-cols-1 sm:grid-cols-3 gap-2 transition-opacity duration-300',
                        feature.enabled ? 'opacity-100' : 'opacity-50',
                      )}
                    >
                      {feature.benefits.map((benefit, i) => {
                        const BenefitIcon = benefit.icon
                        return (
                          <div
                            key={i}
                            className="flex items-center gap-2 text-xs text-slate-400"
                          >
                            <BenefitIcon
                              className={clsx(
                                'w-3.5 h-3.5',
                                feature.enabled
                                  ? feature.color === 'cyan'
                                    ? 'text-cyan/60'
                                    : 'text-magenta/60'
                                  : 'text-slate-600',
                              )}
                            />
                            {benefit.text}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>

                {/* Toggle Switch */}
                <button
                  onClick={feature.toggle}
                  className={clsx(
                    'relative w-12 h-7 rounded-full transition-all duration-300 flex-shrink-0',
                    feature.enabled
                      ? feature.color === 'cyan'
                        ? 'bg-cyan'
                        : 'bg-magenta'
                      : 'bg-void-600',
                  )}
                >
                  <span
                    className={clsx(
                      'absolute top-1 w-5 h-5 rounded-full bg-white shadow-md transition-all duration-300',
                      feature.enabled ? 'left-6' : 'left-1',
                    )}
                  />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Summary */}
      <div className="p-4 rounded-xl bg-void-900/50 border border-void-700/50">
        <h4 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
          Configuration Summary
        </h4>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className={clsx(
                'w-2 h-2 rounded-full',
                data.backupEnabled ? 'bg-cyan' : 'bg-slate-600',
              )}
            />
            <span className={clsx('text-sm', data.backupEnabled ? 'text-slate-200' : 'text-slate-500')}>
              Backups {data.backupEnabled ? 'enabled' : 'disabled'}
            </span>
          </div>
          <div className="w-px h-4 bg-void-600" />
          <div className="flex items-center gap-2">
            <div
              className={clsx(
                'w-2 h-2 rounded-full',
                data.ticketsEnabled ? 'bg-magenta' : 'bg-slate-600',
              )}
            />
            <span className={clsx('text-sm', data.ticketsEnabled ? 'text-slate-200' : 'text-slate-500')}>
              Tickets {data.ticketsEnabled ? 'enabled' : 'disabled'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
