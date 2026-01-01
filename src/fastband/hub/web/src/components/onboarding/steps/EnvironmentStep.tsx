/**
 * Step 1: Environment Configuration
 *
 * Confirms project path and sets up GitHub integration.
 */

import { useEffect, useState, useCallback } from 'react'
import { clsx } from 'clsx'
import {
  FolderGit2,
  Github,
  CheckCircle,
  ExternalLink,
  FolderOpen,
  ChevronRight,
  Home,
  ArrowUp,
  Loader2,
  X,
  Folder,
} from 'lucide-react'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

interface DirectoryEntry {
  name: string
  path: string
  is_dir: boolean
  is_hidden: boolean
}

export function EnvironmentStep({ data, updateData, setStepValid }: StepProps) {
  const [showBrowser, setShowBrowser] = useState(false)
  const [browserPath, setBrowserPath] = useState('')
  const [browserEntries, setBrowserEntries] = useState<DirectoryEntry[]>([])
  const [browserParent, setBrowserParent] = useState<string | null>(null)
  const [browserLoading, setBrowserLoading] = useState(false)
  const [showHidden, setShowHidden] = useState(false)

  // Validate step
  useEffect(() => {
    // Project path is required, GitHub URL is optional
    const isValid = data.projectPath.trim().length > 0
    setStepValid(isValid)
  }, [data.projectPath, setStepValid])

  const validateGithubUrl = (url: string): boolean => {
    if (!url) return true // Optional
    const pattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/
    return pattern.test(url)
  }

  const isGithubValid = validateGithubUrl(data.githubUrl)

  // Fetch directory contents
  const fetchDirectory = useCallback(async (path: string) => {
    setBrowserLoading(true)
    try {
      const response = await fetch('/api/browse/directories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      if (response.ok) {
        const result = await response.json()
        setBrowserPath(result.current_path)
        setBrowserParent(result.parent_path)
        setBrowserEntries(result.entries)
      }
    } catch {
      // Silently handle errors
    } finally {
      setBrowserLoading(false)
    }
  }, [])

  // Open browser at current path or home
  const openBrowser = useCallback(async () => {
    setShowBrowser(true)
    const startPath = data.projectPath || '~'
    await fetchDirectory(startPath)
  }, [data.projectPath, fetchDirectory])

  // Navigate to a directory
  const navigateTo = useCallback((path: string) => {
    fetchDirectory(path)
  }, [fetchDirectory])

  // Select the current directory
  const selectDirectory = useCallback(() => {
    updateData({ projectPath: browserPath })
    setShowBrowser(false)
  }, [browserPath, updateData])

  // Filter entries based on hidden setting
  const filteredEntries = showHidden
    ? browserEntries
    : browserEntries.filter(e => !e.is_hidden)

  return (
    <div className="space-y-6 animate-in">
      {/* Project Path */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
          <FolderGit2 className="w-4 h-4 text-cyan" />
          Project Directory
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={data.projectPath}
              onChange={(e) => updateData({ projectPath: e.target.value })}
              placeholder="/path/to/your/project"
              className="input-field font-mono text-sm pr-10"
            />
            {data.projectPath && (
              <CheckCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400" />
            )}
          </div>
          <button
            type="button"
            onClick={openBrowser}
            className="flex items-center gap-2 px-4 py-2.5 bg-void-700 hover:bg-void-600 border border-void-500 rounded-lg text-slate-300 hover:text-cyan transition-all"
          >
            <FolderOpen className="w-4 h-4" />
            Browse
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          The root directory of your project where Fastband will operate.
        </p>
      </div>

      {/* Directory Browser Modal */}
      {showBrowser && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-xl mx-4 bg-void-800 border border-void-600 rounded-xl shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-void-600">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-cyan" />
                <span className="font-medium text-slate-200">Select Project Directory</span>
              </div>
              <button
                onClick={() => setShowBrowser(false)}
                className="p-1.5 hover:bg-void-700 rounded-lg text-slate-400 hover:text-slate-200 transition-colors"
                aria-label="Close browser"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Current path */}
            <div className="px-4 py-2 bg-void-900/50 border-b border-void-600/50 flex items-center gap-2">
              <span className="text-xs text-slate-500 font-mono truncate flex-1">
                {browserPath}
              </span>
              <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showHidden}
                  onChange={(e) => setShowHidden(e.target.checked)}
                  className="rounded border-void-500 bg-void-700 text-cyan focus:ring-cyan/30"
                />
                Show hidden
              </label>
            </div>

            {/* Navigation buttons */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-void-600/50">
              <button
                onClick={() => navigateTo('~')}
                disabled={browserLoading}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-void-700 hover:bg-void-600 rounded text-slate-300 hover:text-cyan transition-colors disabled:opacity-50"
              >
                <Home className="w-3.5 h-3.5" />
                Home
              </button>
              {browserParent && (
                <button
                  onClick={() => navigateTo(browserParent)}
                  disabled={browserLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-void-700 hover:bg-void-600 rounded text-slate-300 hover:text-cyan transition-colors disabled:opacity-50"
                >
                  <ArrowUp className="w-3.5 h-3.5" />
                  Up
                </button>
              )}
              {browserLoading && (
                <Loader2 className="w-4 h-4 text-cyan animate-spin ml-auto" />
              )}
            </div>

            {/* Directory list */}
            <div className="max-h-64 overflow-y-auto">
              {filteredEntries.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-500">
                  No subdirectories found
                </div>
              ) : (
                <div className="divide-y divide-void-700/50">
                  {filteredEntries.map((entry) => (
                    <button
                      key={entry.path}
                      onClick={() => navigateTo(entry.path)}
                      className={clsx(
                        'w-full flex items-center gap-3 px-4 py-2.5 text-left',
                        'hover:bg-void-700/50 transition-colors',
                        entry.is_hidden && 'opacity-60'
                      )}
                    >
                      <Folder className="w-4 h-4 text-cyan/70 flex-shrink-0" />
                      <span className="text-sm text-slate-300 truncate">{entry.name}</span>
                      <ChevronRight className="w-4 h-4 text-slate-500 ml-auto flex-shrink-0" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-void-600 bg-void-900/30 rounded-b-xl">
              <button
                onClick={() => setShowBrowser(false)}
                className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={selectDirectory}
                className="flex items-center gap-2 px-4 py-2 bg-cyan text-void-900 rounded-lg font-medium text-sm hover:bg-cyan-400 transition-colors"
              >
                <CheckCircle className="w-4 h-4" />
                Select This Directory
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GitHub URL */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
          <Github className="w-4 h-4 text-slate-400" />
          GitHub Repository
          <span className="text-xs text-slate-500 font-normal">(Optional)</span>
        </label>
        <div className="relative">
          <input
            type="text"
            value={data.githubUrl}
            onChange={(e) => updateData({ githubUrl: e.target.value })}
            placeholder="https://github.com/username/repository"
            className={clsx(
              'input-field font-mono text-sm pr-10',
              data.githubUrl && !isGithubValid && 'border-red-500/50 focus:border-red-500/50'
            )}
          />
          {data.githubUrl && isGithubValid && (
            <CheckCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400" />
          )}
        </div>
        {data.githubUrl && !isGithubValid && (
          <p className="mt-2 text-xs text-red-400">
            Please enter a valid GitHub repository URL
          </p>
        )}
        {!data.githubUrl && (
          <p className="mt-2 text-xs text-slate-500">
            Connect your GitHub repository for PR automation and issue tracking.
          </p>
        )}
      </div>

      {/* Info card */}
      <div className="p-4 rounded-xl bg-cyan/5 border border-cyan/20">
        <div className="flex gap-3">
          <div className="w-8 h-8 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
            <FolderGit2 className="w-4 h-4 text-cyan" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-slate-200 mb-1">
              What happens next?
            </h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Fastband will analyze your project structure, detect frameworks and languages,
              and configure appropriate tools. Your project files remain unchanged until you
              explicitly approve any modifications.
            </p>
          </div>
        </div>
      </div>

      {/* GitHub benefits */}
      {data.githubUrl && isGithubValid && (
        <div className="p-4 rounded-xl bg-void-700/50 border border-void-600">
          <h4 className="text-sm font-medium text-slate-200 mb-3 flex items-center gap-2">
            <Github className="w-4 h-4" />
            GitHub Integration Enabled
          </h4>
          <ul className="space-y-2 text-xs text-slate-400">
            <li className="flex items-center gap-2">
              <CheckCircle className="w-3 h-3 text-green-400" />
              Automatic PR creation and review
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-3 h-3 text-green-400" />
              Issue-to-ticket synchronization
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-3 h-3 text-green-400" />
              Branch management automation
            </li>
          </ul>
          <a
            href={data.githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-3 text-xs text-cyan hover:text-cyan-300 transition-colors"
          >
            Open repository
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}
    </div>
  )
}
