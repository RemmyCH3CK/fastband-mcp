/**
 * Step 1: Environment Configuration
 *
 * Confirms project path and sets up GitHub integration.
 */

import { useEffect } from 'react'
import { clsx } from 'clsx'
import { FolderGit2, Github, CheckCircle, ExternalLink } from 'lucide-react'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

export function EnvironmentStep({ data, updateData, setStepValid }: StepProps) {
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

  return (
    <div className="space-y-6 animate-in">
      {/* Project Path */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
          <FolderGit2 className="w-4 h-4 text-cyan" />
          Project Directory
        </label>
        <div className="relative">
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
        <p className="mt-2 text-xs text-slate-500">
          The root directory of your project where Fastband will operate.
        </p>
      </div>

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
