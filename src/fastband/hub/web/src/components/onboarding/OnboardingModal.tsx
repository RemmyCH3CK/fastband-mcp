/**
 * Multi-Step Onboarding Modal for Fastband Hub
 *
 * A non-dismissible wizard that guides new admins through
 * initial setup with Terminal Noir aesthetics.
 */

import { useState, useEffect, useCallback, ReactNode } from 'react'
import { clsx } from 'clsx'
import { ChevronLeft, ChevronRight, Sparkles, Check } from 'lucide-react'
import { StepProgress } from './StepProgress'
import { EnvironmentStep } from './steps/EnvironmentStep'
import { OperationModeStep } from './steps/OperationModeStep'
import { FeaturesStep } from './steps/FeaturesStep'
import { ApiKeysStep } from './steps/ApiKeysStep'
import { AnalyzeStep } from './steps/AnalyzeStep'
import { ToolsStep } from './steps/ToolsStep'

export interface OnboardingData {
  // Step 1: Environment
  projectPath: string
  githubUrl: string
  // Step 2: Operation Mode
  operationMode: 'manual' | 'yolo'
  // Step 3: Features
  backupEnabled: boolean
  ticketsEnabled: boolean
  // Step 4: API Keys
  providers: {
    anthropic: { key: string; valid: boolean }
    openai: { key: string; valid: boolean }
    gemini: { key: string; valid: boolean }
    ollama: { host: string; valid: boolean }
  }
  // Step 5: Analysis
  analysisComplete: boolean
  bibleGenerated: boolean
  techStack: string[]
  // Step 6: Tools
  selectedTools: string[]
  maxRecommendedTools: number
}

const initialData: OnboardingData = {
  projectPath: '',
  githubUrl: '',
  operationMode: 'manual',
  backupEnabled: true,
  ticketsEnabled: true,
  providers: {
    anthropic: { key: '', valid: false },
    openai: { key: '', valid: false },
    gemini: { key: '', valid: false },
    ollama: { host: '', valid: false },
  },
  analysisComplete: false,
  bibleGenerated: false,
  techStack: [],
  selectedTools: [],
  maxRecommendedTools: 60,
}

const STEPS = [
  { id: 'environment', title: 'Environment', subtitle: 'Project Setup' },
  { id: 'operation', title: 'Operation Mode', subtitle: 'Automation Level' },
  { id: 'features', title: 'Features', subtitle: 'Enable Services' },
  { id: 'apikeys', title: 'API Keys', subtitle: 'AI Providers' },
  { id: 'analyze', title: 'Analyze', subtitle: 'Generate Bible' },
  { id: 'tools', title: 'MCP Tools', subtitle: 'Select Tools' },
]

interface OnboardingModalProps {
  isOpen: boolean
  onComplete: (data: OnboardingData) => void
  initialProjectPath?: string
}

export function OnboardingModal({
  isOpen,
  onComplete,
  initialProjectPath = '',
}: OnboardingModalProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [data, setData] = useState<OnboardingData>({
    ...initialData,
    projectPath: initialProjectPath,
  })
  const [stepValid, setStepValid] = useState(false)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const [direction, setDirection] = useState<'forward' | 'back'>('forward')

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  const updateData = useCallback((updates: Partial<OnboardingData>) => {
    setData(prev => ({ ...prev, ...updates }))
  }, [])

  const handleNext = useCallback(() => {
    if (currentStep < STEPS.length - 1) {
      setDirection('forward')
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentStep(prev => prev + 1)
        setIsTransitioning(false)
        setStepValid(false)
      }, 200)
    }
  }, [currentStep])

  const handleBack = useCallback(() => {
    if (currentStep > 0) {
      setDirection('back')
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentStep(prev => prev - 1)
        setIsTransitioning(false)
      }, 200)
    }
  }, [currentStep])

  const handleComplete = useCallback(() => {
    onComplete(data)
  }, [data, onComplete])

  if (!isOpen) return null

  const isLastStep = currentStep === STEPS.length - 1
  const isFirstStep = currentStep === 0

  const renderStep = (): ReactNode => {
    const props = { data, updateData, setStepValid }

    switch (STEPS[currentStep].id) {
      case 'environment':
        return <EnvironmentStep {...props} />
      case 'operation':
        return <OperationModeStep {...props} />
      case 'features':
        return <FeaturesStep {...props} />
      case 'apikeys':
        return <ApiKeysStep {...props} />
      case 'analyze':
        return <AnalyzeStep {...props} />
      case 'tools':
        return <ToolsStep {...props} />
      default:
        return null
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop with animated grid */}
      <div className="absolute inset-0 bg-void-950/95 backdrop-blur-md">
        {/* Animated grid pattern */}
        <div className="absolute inset-0 bg-grid opacity-30" />

        {/* Radial glow from center */}
        <div className="absolute inset-0 bg-gradient-radial from-cyan/5 via-transparent to-transparent" />

        {/* Corner accents */}
        <div className="absolute top-0 left-0 w-64 h-64 bg-gradient-radial from-cyan/10 to-transparent opacity-50" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-gradient-radial from-magenta/10 to-transparent opacity-30" />

        {/* Scan line effect */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-cyan/30 to-transparent"
            style={{
              animation: 'scanVertical 8s linear infinite',
            }}
          />
        </div>
      </div>

      {/* Modal Container */}
      <div
        className={clsx(
          'relative w-full max-w-3xl mx-4',
          'bg-void-800/95 backdrop-blur-xl border border-void-600/50 rounded-2xl',
          'shadow-[0_0_100px_rgba(0,0,0,0.8),0_0_60px_rgba(0,212,255,0.08)]',
        )}
        style={{
          animation: 'modalSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Top glow line */}
        <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-cyan/60 to-transparent" />

        {/* Corner decorations */}
        <div className="absolute top-4 left-4 w-8 h-8 border-l-2 border-t-2 border-cyan/30 rounded-tl-lg" />
        <div className="absolute top-4 right-4 w-8 h-8 border-r-2 border-t-2 border-cyan/30 rounded-tr-lg" />
        <div className="absolute bottom-4 left-4 w-8 h-8 border-l-2 border-b-2 border-magenta/30 rounded-bl-lg" />
        <div className="absolute bottom-4 right-4 w-8 h-8 border-r-2 border-b-2 border-magenta/30 rounded-br-lg" />

        {/* Header */}
        <div className="px-8 pt-8 pb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan/20 via-void-700 to-magenta/20 border border-cyan/30 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-cyan" />
            </div>
            <div>
              <h1 className="text-xl font-display font-bold text-slate-100">
                Welcome to Fastband
              </h1>
              <p className="text-sm text-slate-400">
                Let's configure your AI-powered development environment
              </p>
            </div>
          </div>

          {/* Step Progress */}
          <StepProgress
            steps={STEPS}
            currentStep={currentStep}
          />
        </div>

        {/* Step Title */}
        <div className="px-8 pb-4 border-b border-void-600/50">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-cyan/60 uppercase tracking-wider">
              Step {currentStep + 1} of {STEPS.length}
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">
              {STEPS[currentStep].subtitle}
            </span>
          </div>
          <h2 className="text-2xl font-display font-semibold text-slate-100 mt-1">
            {STEPS[currentStep].title}
          </h2>
        </div>

        {/* Content */}
        <div
          className={clsx(
            'px-8 py-6 min-h-[320px] transition-all duration-200',
            isTransitioning && direction === 'forward' && 'opacity-0 translate-x-4',
            isTransitioning && direction === 'back' && 'opacity-0 -translate-x-4',
          )}
        >
          {renderStep()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-8 py-6 border-t border-void-600/50 bg-void-900/50 rounded-b-2xl">
          <button
            onClick={handleBack}
            disabled={isFirstStep}
            className={clsx(
              'flex items-center gap-2 px-4 py-2.5 rounded-lg',
              'text-slate-300 font-medium',
              'transition-all duration-200',
              isFirstStep
                ? 'opacity-0 cursor-default'
                : 'hover:bg-void-700 hover:text-cyan'
            )}
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </button>

          <div className="flex items-center gap-3">
            {isLastStep ? (
              <button
                onClick={handleComplete}
                disabled={!stepValid}
                className={clsx(
                  'flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium',
                  'transition-all duration-200',
                  stepValid
                    ? 'bg-gradient-to-r from-cyan to-cyan-400 text-void-900 shadow-glow-cyan hover:shadow-[0_0_30px_rgba(0,212,255,0.5)]'
                    : 'bg-void-700 text-slate-500 cursor-not-allowed'
                )}
              >
                <Check className="w-4 h-4" />
                Complete Setup
              </button>
            ) : (
              <button
                onClick={handleNext}
                disabled={!stepValid}
                className={clsx(
                  'flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium',
                  'transition-all duration-200',
                  stepValid
                    ? 'bg-cyan text-void-900 hover:shadow-glow-cyan'
                    : 'bg-void-700 text-slate-500 cursor-not-allowed'
                )}
              >
                Continue
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes modalSlideIn {
          from {
            opacity: 0;
            transform: translateY(-30px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        @keyframes scanVertical {
          0% { top: -2px; }
          100% { top: 100%; }
        }
      `}</style>
    </div>
  )
}
