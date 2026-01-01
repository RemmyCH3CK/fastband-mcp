/**
 * Step 2: Operation Mode Selection
 *
 * Choose between Manual mode (human confirms all actions)
 * or YOLO mode (full automation with Agent Bible guardrails).
 */

import { useEffect } from 'react'
import { clsx } from 'clsx'
import {
  Shield,
  Zap,
  User,
  Bot,
  CheckCircle,
  AlertTriangle,
  GitPullRequest,
  GitMerge,
  Rocket,
  MessageSquare,
} from 'lucide-react'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

export function OperationModeStep({ data, updateData, setStepValid }: StepProps) {
  // Always valid - there's a default selection
  useEffect(() => {
    setStepValid(true)
  }, [setStepValid])

  const modes = [
    {
      id: 'manual' as const,
      name: 'Manual Mode',
      icon: Shield,
      color: 'cyan',
      description: 'You confirm every action before agents execute',
      features: [
        { icon: MessageSquare, text: 'Review changes in chat before applying' },
        { icon: User, text: 'Approve commits, PRs, and deployments' },
        { icon: CheckCircle, text: 'Maximum control and visibility' },
      ],
      recommended: false,
    },
    {
      id: 'yolo' as const,
      name: 'YOLO Mode',
      icon: Zap,
      color: 'magenta',
      description: 'Full automation within Agent Bible guardrails',
      features: [
        { icon: Bot, text: 'Agents work autonomously on tickets' },
        { icon: GitPullRequest, text: 'Auto-create PRs and branches' },
        { icon: GitMerge, text: 'Merge and deploy when ready' },
        { icon: Rocket, text: 'Ship faster with AI guardrails' },
      ],
      recommended: true,
    },
  ]

  return (
    <div className="space-y-6 animate-in">
      <p className="text-sm text-slate-400">
        Choose how much autonomy you want to give AI agents when working on your codebase.
      </p>

      {/* Mode cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {modes.map((mode) => {
          const isSelected = data.operationMode === mode.id
          const Icon = mode.icon

          return (
            <button
              key={mode.id}
              onClick={() => updateData({ operationMode: mode.id })}
              className={clsx(
                'relative p-5 rounded-xl border text-left transition-all duration-300',
                'hover:scale-[1.02]',
                isSelected
                  ? mode.color === 'cyan'
                    ? 'bg-cyan/10 border-cyan/50 shadow-glow-cyan'
                    : 'bg-magenta/10 border-magenta/50 shadow-glow-magenta'
                  : 'bg-void-800/50 border-void-600/50 hover:border-void-500',
              )}
            >
              {/* Recommended badge */}
              {mode.recommended && (
                <div className="absolute -top-2 -right-2 px-2 py-0.5 rounded-full bg-magenta text-void-900 text-xs font-bold">
                  Recommended
                </div>
              )}

              {/* Header */}
              <div className="flex items-center gap-3 mb-3">
                <div
                  className={clsx(
                    'w-10 h-10 rounded-xl flex items-center justify-center',
                    mode.color === 'cyan'
                      ? 'bg-cyan/20 text-cyan'
                      : 'bg-magenta/20 text-magenta',
                  )}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-slate-100">
                    {mode.name}
                  </h3>
                  <p className="text-xs text-slate-500">{mode.description}</p>
                </div>
              </div>

              {/* Features */}
              <ul className="space-y-2">
                {mode.features.map((feature, i) => {
                  const FeatureIcon = feature.icon
                  return (
                    <li key={i} className="flex items-center gap-2 text-xs text-slate-400">
                      <FeatureIcon className="w-3.5 h-3.5 text-slate-500" />
                      {feature.text}
                    </li>
                  )
                })}
              </ul>

              {/* Selection indicator */}
              {isSelected && (
                <div
                  className={clsx(
                    'absolute bottom-3 right-3 w-5 h-5 rounded-full flex items-center justify-center',
                    mode.color === 'cyan' ? 'bg-cyan text-void-900' : 'bg-magenta text-void-900',
                  )}
                >
                  <CheckCircle className="w-3 h-3" />
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* YOLO Mode Warning */}
      {data.operationMode === 'yolo' && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 animate-in">
          <div className="flex gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-amber-300 mb-1">
                Agent Bible Guardrails
              </h4>
              <p className="text-xs text-amber-200/70 leading-relaxed">
                In YOLO mode, agents follow rules defined in your Agent Bible. After setup,
                you can add custom "laws" that agents must obey - like never modifying
                certain files, requiring tests, or limiting deployment to specific branches.
              </p>
              <p className="text-xs text-slate-400 mt-2">
                You can edit the Agent Bible anytime from the Hub dashboard.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Manual Mode Info */}
      {data.operationMode === 'manual' && (
        <div className="p-4 rounded-xl bg-cyan/5 border border-cyan/20 animate-in">
          <div className="flex gap-3">
            <Shield className="w-5 h-5 text-cyan flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-cyan mb-1">
                Full Control Mode
              </h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Every action will require your explicit approval. Agents will present
                their proposed changes in the chat, and you decide what gets applied.
                This is ideal for sensitive codebases or when learning how agents work.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
