import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  Zap,
  FolderGit2,
  Globe,
  ArrowRight,
  Check,
  Loader2,
  Github,
} from 'lucide-react'
import { useSessionStore } from '../stores/session'

type Step = 'welcome' | 'source' | 'analyzing' | 'complete'
type SourceType = 'local' | 'github' | 'new'

interface AnalysisResult {
  languages: string[]
  frameworks: string[]
  tools: string[]
  recommendations: string[]
}

export function Onboarding() {
  const [step, setStep] = useState<Step>('welcome')
  const [sourceType, setSourceType] = useState<SourceType | null>(null)
  const [path, setPath] = useState('')
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [_loading, setLoading] = useState(false) // Loading state tracked for potential future UI use
  const [error, setError] = useState('')

  const navigate = useNavigate()
  const { sessionId } = useSessionStore()

  const handleSourceSelect = (type: SourceType) => {
    setSourceType(type)
    if (type === 'new') {
      setStep('complete')
    }
  }

  const handleAnalyze = async () => {
    if (!path.trim()) {
      setError('Please enter a path or URL')
      return
    }

    setLoading(true)
    setError('')
    setStep('analyzing')

    try {
      const endpoint =
        sourceType === 'github' ? '/api/analyze/github' : '/api/analyze/local'

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          [sourceType === 'github' ? 'repo_url' : 'path']: path,
        }),
      })

      if (!response.ok) {
        throw new Error('Analysis failed')
      }

      const data = await response.json()
      setAnalysis(data)
      setStep('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
      setStep('source')
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = () => {
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Progress indicator */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {['welcome', 'source', 'complete'].map((s, i) => (
            <div
              key={s}
              className={clsx(
                'w-3 h-3 rounded-full transition-colors',
                step === s || (step === 'analyzing' && s === 'source')
                  ? 'bg-blue-500'
                  : i < ['welcome', 'source', 'complete'].indexOf(step)
                  ? 'bg-green-500'
                  : 'bg-gray-700'
              )}
            />
          ))}
        </div>

        {/* Welcome step */}
        {step === 'welcome' && (
          <div className="text-center">
            <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-6">
              <Zap className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-4">
              Welcome to Fastband AI Hub
            </h1>
            <p className="text-gray-400 mb-8 max-w-md mx-auto">
              Your AI-powered development assistant. Let's set up your workspace
              and configure the tools you need.
            </p>
            <button
              onClick={() => setStep('source')}
              className={clsx(
                'inline-flex items-center gap-2 px-6 py-3 rounded-lg',
                'bg-blue-600 text-white font-medium',
                'hover:bg-blue-700 transition-colors'
              )}
            >
              Get Started
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Source selection step */}
        {step === 'source' && (
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-white mb-2">
              Connect Your Project
            </h2>
            <p className="text-gray-400 mb-6">
              Choose how you want to connect your codebase for AI-assisted
              development.
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
                {error}
              </div>
            )}

            <div className="grid gap-4 mb-6">
              <button
                onClick={() => handleSourceSelect('local')}
                className={clsx(
                  'flex items-center gap-4 p-4 rounded-lg border-2 transition-colors text-left',
                  sourceType === 'local'
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-gray-700 hover:border-gray-600'
                )}
              >
                <div className="w-12 h-12 rounded-lg bg-gray-700 flex items-center justify-center">
                  <FolderGit2 className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="font-medium text-white">Local Directory</h3>
                  <p className="text-sm text-gray-400">
                    Connect a project from your local machine
                  </p>
                </div>
              </button>

              <button
                onClick={() => handleSourceSelect('github')}
                className={clsx(
                  'flex items-center gap-4 p-4 rounded-lg border-2 transition-colors text-left',
                  sourceType === 'github'
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-gray-700 hover:border-gray-600'
                )}
              >
                <div className="w-12 h-12 rounded-lg bg-gray-700 flex items-center justify-center">
                  <Github className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <h3 className="font-medium text-white">GitHub Repository</h3>
                  <p className="text-sm text-gray-400">
                    Connect a repository from GitHub
                  </p>
                </div>
              </button>

              <button
                onClick={() => handleSourceSelect('new')}
                className={clsx(
                  'flex items-center gap-4 p-4 rounded-lg border-2 transition-colors text-left',
                  sourceType === 'new'
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-gray-700 hover:border-gray-600'
                )}
              >
                <div className="w-12 h-12 rounded-lg bg-gray-700 flex items-center justify-center">
                  <Globe className="w-6 h-6 text-green-400" />
                </div>
                <div>
                  <h3 className="font-medium text-white">Start Fresh</h3>
                  <p className="text-sm text-gray-400">
                    Create a new project from scratch with AI guidance
                  </p>
                </div>
              </button>
            </div>

            {(sourceType === 'local' || sourceType === 'github') && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    {sourceType === 'github' ? 'Repository URL' : 'Directory Path'}
                  </label>
                  <input
                    type="text"
                    value={path}
                    onChange={(e) => setPath(e.target.value)}
                    placeholder={
                      sourceType === 'github'
                        ? 'https://github.com/user/repo'
                        : '/path/to/project'
                    }
                    className={clsx(
                      'w-full px-4 py-3 rounded-lg',
                      'bg-gray-700 border border-gray-600 text-white',
                      'focus:border-blue-500 focus:outline-none'
                    )}
                  />
                </div>

                <button
                  onClick={handleAnalyze}
                  disabled={!path.trim()}
                  className={clsx(
                    'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg',
                    'bg-blue-600 text-white font-medium',
                    'hover:bg-blue-700 transition-colors',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  Analyze Project
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Analyzing step */}
        {step === 'analyzing' && (
          <div className="bg-gray-800 rounded-lg p-8 text-center">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-white mb-2">
              Analyzing Your Project
            </h2>
            <p className="text-gray-400">
              Scanning files, detecting frameworks, and preparing recommendations...
            </p>
          </div>
        )}

        {/* Complete step */}
        {step === 'complete' && (
          <div className="bg-gray-800 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                <Check className="w-6 h-6 text-green-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">
                  {analysis ? 'Analysis Complete' : 'Ready to Go'}
                </h2>
                <p className="text-gray-400">
                  {analysis
                    ? "Here's what we found in your project"
                    : 'Your workspace is configured'}
                </p>
              </div>
            </div>

            {analysis && (
              <div className="space-y-4 mb-6">
                {analysis.languages.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-400 mb-2">
                      Languages
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {analysis.languages.map((lang) => (
                        <span
                          key={lang}
                          className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-sm"
                        >
                          {lang}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysis.frameworks.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-400 mb-2">
                      Frameworks
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {analysis.frameworks.map((fw) => (
                        <span
                          key={fw}
                          className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-sm"
                        >
                          {fw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysis.recommendations.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-400 mb-2">
                      Recommended Tools
                    </h3>
                    <ul className="space-y-2">
                      {analysis.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-gray-300">
                          <Check className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <button
              onClick={handleComplete}
              className={clsx(
                'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg',
                'bg-blue-600 text-white font-medium',
                'hover:bg-blue-700 transition-colors'
              )}
            >
              Continue to Chat
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
