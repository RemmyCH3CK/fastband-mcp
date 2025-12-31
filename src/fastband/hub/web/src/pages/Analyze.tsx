import { useState } from 'react'
import { clsx } from 'clsx'
import {
  FolderGit2,
  Github,
  Play,
  Loader2,
  FileCode,
  Package,
  GitBranch,
  Server,
  Check,
  AlertCircle,
} from 'lucide-react'
import { Layout } from '../components/Layout'

interface AnalysisResult {
  report_id: string
  project_name: string
  connection_type: string
  phase: string
  summary: string
  confidence: number
  warnings: string[]
  tech_stack: {
    primary_language: string
    languages: { [key: string]: number }
    frameworks: string[]
    databases: string[]
    ci_cd: string[]
    testing: string[]
    package_managers: string[]
  } | null
  workflow: {
    has_git: boolean
    default_branch: string
    has_ci: boolean
    has_tests: boolean
    has_docs: boolean
    has_docker: boolean
    has_kubernetes: boolean
  } | null
  recommendations: Array<{
    tool_category: string
    tools: string[]
    priority: string
    rationale: string
    configuration: Record<string, unknown>
  }>
  file_stats: {
    total_files: number
    total_lines: number
    by_extension: { [key: string]: number }
    by_directory: { [key: string]: number }
  } | null
}

export function Analyze() {
  const [sourceType, setSourceType] = useState<'local' | 'github'>('local')
  const [path, setPath] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)

  const handleAnalyze = async () => {
    if (!path.trim()) {
      setError('Please enter a path or URL')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          sourceType === 'github'
            ? { github_url: path }
            : { path: path }
        ),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Analysis failed')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const priorityColors: Record<string, string> = {
    essential: 'bg-red-500/20 text-red-300 border-red-500/50',
    recommended: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50',
    optional: 'bg-green-500/20 text-green-300 border-green-500/50',
  }

  return (
    <Layout>
      <div className="h-full overflow-auto">
        <div className="max-w-4xl mx-auto p-6">
          <h1 className="text-2xl font-bold text-white mb-2">Platform Analyzer</h1>
          <p className="text-gray-400 mb-6">
            Analyze your codebase to get MCP tool recommendations and workflow
            suggestions.
          </p>

          {/* Source Selection */}
          <div className="bg-gray-800 rounded-lg p-6 mb-6">
            <div className="flex gap-4 mb-4">
              <button
                onClick={() => setSourceType('local')}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                  sourceType === 'local'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                )}
              >
                <FolderGit2 className="w-4 h-4" />
                Local Directory
              </button>
              <button
                onClick={() => setSourceType('github')}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                  sourceType === 'github'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                )}
              >
                <Github className="w-4 h-4" />
                GitHub Repository
              </button>
            </div>

            <div className="flex gap-3">
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
                  'flex-1 px-4 py-3 rounded-lg',
                  'bg-gray-700 border border-gray-600 text-white',
                  'focus:border-blue-500 focus:outline-none'
                )}
              />
              <button
                onClick={handleAnalyze}
                disabled={loading || !path.trim()}
                className={clsx(
                  'flex items-center gap-2 px-6 py-3 rounded-lg',
                  'bg-blue-600 text-white font-medium',
                  'hover:bg-blue-700 transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Play className="w-5 h-5" />
                )}
                Analyze
              </button>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded flex items-center gap-2 text-red-200 text-sm">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
          </div>

          {/* Results */}
          {result && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <FileCode className="w-5 h-5 text-blue-400" />
                  Analysis Summary: {result.project_name}
                </h2>
                <p className="text-gray-300 mb-4">{result.summary}</p>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-gray-700 rounded-lg">
                    <p className="text-3xl font-bold text-white">
                      {result.file_stats?.total_files.toLocaleString() ?? 0}
                    </p>
                    <p className="text-sm text-gray-400">Files analyzed</p>
                  </div>
                  <div className="p-4 bg-gray-700 rounded-lg">
                    <p className="text-3xl font-bold text-white">
                      {result.file_stats?.total_lines.toLocaleString() ?? 0}
                    </p>
                    <p className="text-sm text-gray-400">Lines of code</p>
                  </div>
                  <div className="p-4 bg-gray-700 rounded-lg">
                    <p className="text-3xl font-bold text-white">
                      {Math.round(result.confidence * 100)}%
                    </p>
                    <p className="text-sm text-gray-400">Confidence</p>
                  </div>
                </div>
                {result.warnings.length > 0 && (
                  <div className="mt-4 p-3 bg-yellow-900/30 border border-yellow-700 rounded">
                    <p className="text-yellow-300 text-sm">{result.warnings.join(', ')}</p>
                  </div>
                )}
              </div>

              {/* Tech Stack */}
              {result.tech_stack && (
                <div className="bg-gray-800 rounded-lg p-6">
                  <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Package className="w-5 h-5 text-purple-400" />
                    Tech Stack
                  </h2>
                  <div className="grid md:grid-cols-2 gap-4">
                    {Object.keys(result.tech_stack.languages).length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-2">
                          Languages
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(result.tech_stack.languages).map(([lang, pct]) => (
                            <span
                              key={lang}
                              className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-sm"
                            >
                              {lang} ({pct}%)
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {result.tech_stack.frameworks.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-2">
                          Frameworks
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {result.tech_stack.frameworks.map((fw) => (
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
                    {result.tech_stack.databases.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-2">
                          Databases
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {result.tech_stack.databases.map((db) => (
                            <span
                              key={db}
                              className="px-3 py-1 rounded-full bg-green-500/20 text-green-300 text-sm"
                            >
                              {db}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {result.tech_stack.ci_cd.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-2">
                          CI/CD
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {result.tech_stack.ci_cd.map((ci) => (
                            <span
                              key={ci}
                              className="px-3 py-1 rounded-full bg-orange-500/20 text-orange-300 text-sm"
                            >
                              {ci}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Workflow Info */}
              {result.workflow && (
                <div className="bg-gray-800 rounded-lg p-6">
                  <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <GitBranch className="w-5 h-5 text-yellow-400" />
                    Workflow Features
                  </h2>
                  <div className="flex flex-wrap gap-3">
                    {result.workflow.has_git && (
                      <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-green-500/20 text-green-300 text-sm">
                        <Check className="w-4 h-4" /> Git ({result.workflow.default_branch})
                      </span>
                    )}
                    {result.workflow.has_ci && (
                      <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-green-500/20 text-green-300 text-sm">
                        <Check className="w-4 h-4" /> CI/CD
                      </span>
                    )}
                    {result.workflow.has_tests && (
                      <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-green-500/20 text-green-300 text-sm">
                        <Check className="w-4 h-4" /> Tests
                      </span>
                    )}
                    {result.workflow.has_docker && (
                      <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-green-500/20 text-green-300 text-sm">
                        <Check className="w-4 h-4" /> Docker
                      </span>
                    )}
                    {result.workflow.has_docs && (
                      <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-green-500/20 text-green-300 text-sm">
                        <Check className="w-4 h-4" /> Documentation
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Server className="w-5 h-5 text-green-400" />
                  MCP Tool Recommendations
                </h2>
                <div className="space-y-3">
                  {result.recommendations.map((rec, i) => (
                    <div
                      key={i}
                      className={clsx(
                        'p-4 rounded-lg border',
                        priorityColors[rec.priority] || 'bg-gray-700 border-gray-600'
                      )}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-medium capitalize">{rec.tool_category}</h3>
                        <span className="text-xs uppercase">{rec.priority}</span>
                      </div>
                      <p className="text-sm opacity-80 mb-2">{rec.rationale}</p>
                      <div className="flex flex-wrap gap-2">
                        {rec.tools.map((tool) => (
                          <span
                            key={tool}
                            className="px-2 py-1 rounded bg-gray-600 text-gray-300 text-xs"
                          >
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
