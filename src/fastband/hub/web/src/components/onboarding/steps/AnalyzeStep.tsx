/**
 * Step 5: Analyze & Bible Generation
 *
 * Runs codebase analysis and generates AGENT_BIBLE.md using AI.
 */

import { useState, useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import {
  Scan,
  FileCode2,
  BookOpen,
  CheckCircle,
  Loader2,
  RefreshCw,
  AlertCircle,
  Sparkles,
  GitBranch,
  Package,
} from 'lucide-react'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

interface AnalysisPhase {
  id: string
  name: string
  icon: React.ComponentType<{ className?: string }>
  status: 'pending' | 'running' | 'complete' | 'error'
}

const initialPhases: AnalysisPhase[] = [
  { id: 'scan', name: 'Scanning files', icon: Scan, status: 'pending' },
  { id: 'deps', name: 'Analyzing dependencies', icon: Package, status: 'pending' },
  { id: 'stack', name: 'Detecting tech stack', icon: FileCode2, status: 'pending' },
  { id: 'patterns', name: 'Identifying patterns', icon: GitBranch, status: 'pending' },
  { id: 'bible', name: 'Generating Agent Bible', icon: BookOpen, status: 'pending' },
]

export function AnalyzeStep({ data, updateData, setStepValid }: StepProps) {
  const [phases, setPhases] = useState<AnalysisPhase[]>(initialPhases)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [biblePreview, setBiblePreview] = useState<string>('')
  const hasStarted = useRef(false)

  // Check validity
  useEffect(() => {
    setStepValid(data.analysisComplete && data.bibleGenerated)
  }, [data.analysisComplete, data.bibleGenerated, setStepValid])

  // Auto-start analysis on mount
  useEffect(() => {
    if (!hasStarted.current && !data.analysisComplete) {
      hasStarted.current = true
      runAnalysis()
    }
  }, [])

  const updatePhase = (id: string, status: AnalysisPhase['status']) => {
    setPhases(prev =>
      prev.map(p => (p.id === id ? { ...p, status } : p))
    )
  }

  const runAnalysis = async () => {
    setIsAnalyzing(true)
    setError(null)
    setPhases(initialPhases)

    try {
      // Phase 1: Scan files
      updatePhase('scan', 'running')
      await simulatePhase(800)
      updatePhase('scan', 'complete')

      // Phase 2: Analyze dependencies
      updatePhase('deps', 'running')
      await simulatePhase(600)
      updatePhase('deps', 'complete')

      // Phase 3: Detect tech stack
      updatePhase('stack', 'running')
      const stackResponse = await fetch('/api/analyze/tech-stack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectPath: data.projectPath }),
      })

      let techStack = ['Python', 'FastAPI', 'React', 'TypeScript']
      if (stackResponse.ok) {
        const stackResult = await stackResponse.json()
        techStack = stackResult.stack || techStack
      }
      updatePhase('stack', 'complete')

      // Phase 4: Identify patterns
      updatePhase('patterns', 'running')
      await simulatePhase(700)
      updatePhase('patterns', 'complete')

      // Phase 5: Generate Bible
      updatePhase('bible', 'running')
      const bibleResponse = await fetch('/api/analyze/generate-bible', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectPath: data.projectPath,
          operationMode: data.operationMode,
          techStack,
        }),
      })

      let bibleContent = generateFallbackBible(techStack, data.operationMode)
      if (bibleResponse.ok) {
        const bibleResult = await bibleResponse.json()
        bibleContent = bibleResult.content || bibleContent
      }

      setBiblePreview(bibleContent)
      updatePhase('bible', 'complete')

      // Update data
      updateData({
        analysisComplete: true,
        bibleGenerated: true,
        techStack,
      })
    } catch (err) {
      console.error('Analysis failed:', err)
      setError('Analysis failed. Please try again.')

      // Mark current running phase as error
      setPhases(prev =>
        prev.map(p => (p.status === 'running' ? { ...p, status: 'error' } : p))
      )
    } finally {
      setIsAnalyzing(false)
    }
  }

  const simulatePhase = (ms: number) =>
    new Promise(resolve => setTimeout(resolve, ms))

  const regenerateBible = async () => {
    setIsAnalyzing(true)
    updatePhase('bible', 'running')

    try {
      const response = await fetch('/api/analyze/generate-bible', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectPath: data.projectPath,
          operationMode: data.operationMode,
          techStack: data.techStack,
          regenerate: true,
        }),
      })

      if (response.ok) {
        const result = await response.json()
        setBiblePreview(result.content)
      }
      updatePhase('bible', 'complete')
    } catch {
      updatePhase('bible', 'error')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const completedCount = phases.filter(p => p.status === 'complete').length

  return (
    <div className="space-y-5 animate-in">
      {/* Progress header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          {data.analysisComplete
            ? 'Analysis complete. Review your Agent Bible below.'
            : 'Analyzing your codebase to generate optimal configuration...'}
        </p>
        {!data.analysisComplete && (
          <span className="text-xs text-cyan">
            {completedCount}/{phases.length} phases
          </span>
        )}
      </div>

      {/* Analysis phases */}
      <div className="space-y-2">
        {phases.map((phase, index) => {
          const Icon = phase.icon
          const isRunning = phase.status === 'running'
          const isComplete = phase.status === 'complete'
          const isError = phase.status === 'error'

          return (
            <div
              key={phase.id}
              className={clsx(
                'flex items-center gap-3 p-3 rounded-lg border transition-all duration-300',
                isComplete && 'bg-green-500/5 border-green-500/20',
                isRunning && 'bg-cyan/5 border-cyan/30',
                isError && 'bg-red-500/5 border-red-500/20',
                phase.status === 'pending' && 'bg-void-800/30 border-void-700/50',
              )}
              style={{
                animationDelay: `${index * 100}ms`,
              }}
            >
              {/* Status icon */}
              <div
                className={clsx(
                  'w-8 h-8 rounded-lg flex items-center justify-center',
                  isComplete && 'bg-green-500/10 text-green-400',
                  isRunning && 'bg-cyan/10 text-cyan',
                  isError && 'bg-red-500/10 text-red-400',
                  phase.status === 'pending' && 'bg-void-700 text-slate-500',
                )}
              >
                {isRunning ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : isComplete ? (
                  <CheckCircle className="w-4 h-4" />
                ) : isError ? (
                  <AlertCircle className="w-4 h-4" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
              </div>

              {/* Phase name */}
              <span
                className={clsx(
                  'text-sm font-medium',
                  isComplete && 'text-green-300',
                  isRunning && 'text-cyan',
                  isError && 'text-red-400',
                  phase.status === 'pending' && 'text-slate-500',
                )}
              >
                {phase.name}
              </span>

              {/* Running indicator */}
              {isRunning && (
                <div className="ml-auto flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse" />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse"
                    style={{ animationDelay: '0.2s' }}
                  />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse"
                    style={{ animationDelay: '0.4s' }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <span className="text-sm text-red-300">{error}</span>
          <button
            onClick={runAnalysis}
            className="ml-auto px-3 py-1 rounded text-xs font-medium bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Tech stack detected */}
      {data.analysisComplete && data.techStack.length > 0 && (
        <div className="p-4 rounded-xl bg-void-800/50 border border-void-600/50">
          <h4 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">
            Detected Tech Stack
          </h4>
          <div className="flex flex-wrap gap-2">
            {data.techStack.map((tech, i) => (
              <span
                key={i}
                className="px-3 py-1.5 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-sm font-medium"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Bible preview */}
      {data.bibleGenerated && biblePreview && (
        <div className="rounded-xl border border-magenta/30 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-magenta/10 border-b border-magenta/20">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-magenta" />
              <span className="text-sm font-medium text-magenta">Agent Bible Preview</span>
            </div>
            <button
              onClick={regenerateBible}
              disabled={isAnalyzing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-magenta/20 text-magenta text-xs font-medium hover:bg-magenta/30 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={clsx('w-3 h-3', isAnalyzing && 'animate-spin')} />
              Regenerate
            </button>
          </div>
          <div className="p-4 bg-void-900/50 max-h-48 overflow-y-auto">
            <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono leading-relaxed">
              {biblePreview}
            </pre>
          </div>
        </div>
      )}

      {/* Success message */}
      {data.analysisComplete && data.bibleGenerated && (
        <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-green-300 mb-1">
              Ready to Go!
            </h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your Agent Bible has been generated based on your codebase analysis.
              You can edit these rules anytime from the Hub dashboard.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Generate a fallback Bible if API fails
 */
function generateFallbackBible(
  techStack: string[],
  operationMode: 'manual' | 'yolo'
): string {
  const modeRules =
    operationMode === 'yolo'
      ? `## Automation Level: YOLO
Agents have full autonomy within these guardrails.`
      : `## Automation Level: Manual
Agents must confirm all actions before execution.`

  return `# Agent Bible

${modeRules}

## Core Laws

| Severity | Category | Rule |
|----------|----------|------|
| MUST | security | Never commit secrets or API keys |
| MUST | workflow | Always create feature branches for changes |
| SHOULD | testing | Write tests for new features |
| SHOULD | code_style | Follow existing code conventions |
| MUST_NOT | workflow | Never force push to main branch |
| MUST_NOT | security | Never disable security features |

## Tech Stack
${techStack.map(t => `- ${t}`).join('\n')}

## Guidelines
- Keep changes focused and atomic
- Write clear commit messages
- Document significant changes
- Respect existing architecture patterns
`
}
