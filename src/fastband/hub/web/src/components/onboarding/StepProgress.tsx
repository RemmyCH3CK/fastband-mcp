/**
 * Step Progress Indicator
 *
 * Visual representation of onboarding progress with
 * glowing connectors and animated transitions.
 */

import { clsx } from 'clsx'
import { Check } from 'lucide-react'

interface Step {
  id: string
  title: string
  subtitle: string
}

interface StepProgressProps {
  steps: Step[]
  currentStep: number
}

export function StepProgress({ steps, currentStep }: StepProgressProps) {
  return (
    <div className="relative">
      {/* Progress bar background */}
      <div className="absolute top-4 left-0 right-0 h-0.5 bg-void-700" />

      {/* Animated progress fill */}
      <div
        className="absolute top-4 left-0 h-0.5 bg-gradient-to-r from-cyan via-cyan to-cyan/50 transition-all duration-500 ease-out"
        style={{
          width: `${(currentStep / (steps.length - 1)) * 100}%`,
          boxShadow: '0 0 10px rgba(0, 212, 255, 0.5)',
        }}
      />

      {/* Step indicators */}
      <div className="relative flex justify-between">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep
          const isCurrent = index === currentStep
          const isPending = index > currentStep

          return (
            <div key={step.id} className="flex flex-col items-center">
              {/* Step circle */}
              <div
                className={clsx(
                  'relative w-8 h-8 rounded-full flex items-center justify-center',
                  'transition-all duration-300',
                  isCompleted && 'bg-cyan text-void-900',
                  isCurrent && 'bg-void-700 border-2 border-cyan text-cyan',
                  isPending && 'bg-void-800 border border-void-600 text-slate-500',
                )}
                style={{
                  boxShadow: isCurrent
                    ? '0 0 20px rgba(0, 212, 255, 0.4), inset 0 0 10px rgba(0, 212, 255, 0.1)'
                    : isCompleted
                    ? '0 0 15px rgba(0, 212, 255, 0.3)'
                    : 'none',
                }}
              >
                {isCompleted ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <span className="text-xs font-mono font-bold">{index + 1}</span>
                )}

                {/* Pulse ring for current step */}
                {isCurrent && (
                  <div
                    className="absolute inset-0 rounded-full border border-cyan"
                    style={{
                      animation: 'stepPulse 2s ease-out infinite',
                    }}
                  />
                )}
              </div>

              {/* Step label - only show for current and adjacent steps on mobile */}
              <div
                className={clsx(
                  'mt-2 text-center transition-all duration-300',
                  'hidden sm:block',
                  isCurrent && 'opacity-100',
                  !isCurrent && 'opacity-50',
                )}
              >
                <p
                  className={clsx(
                    'text-xs font-medium',
                    isCurrent ? 'text-cyan' : isCompleted ? 'text-slate-300' : 'text-slate-500',
                  )}
                >
                  {step.title}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <style>{`
        @keyframes stepPulse {
          0% {
            transform: scale(1);
            opacity: 0.8;
          }
          100% {
            transform: scale(1.8);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  )
}
