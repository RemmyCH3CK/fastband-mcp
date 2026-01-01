/**
 * Step 6: MCP Tools Selection
 *
 * Select tools with performance meter showing resource impact.
 */

import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  Check,
  Wrench,
  FileCode,
  GitBranch,
  Terminal,
  Globe,
  FolderTree,
  Sparkles,
  Shield,
} from 'lucide-react'
import { PerformanceMeter } from '../PerformanceMeter'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

interface ToolCategory {
  id: string
  name: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  tools: Tool[]
}

interface Tool {
  id: string
  name: string
  description: string
  essential: boolean
  resourceHint?: 'low' | 'medium' | 'high'
}

const toolCategories: ToolCategory[] = [
  {
    id: 'file',
    name: 'File Operations',
    icon: FileCode,
    color: 'cyan',
    tools: [
      { id: 'read_file', name: 'Read File', description: 'Read file contents', essential: true },
      { id: 'write_file', name: 'Write File', description: 'Write to files', essential: true },
      { id: 'edit_file', name: 'Edit File', description: 'Edit file sections', essential: true },
      { id: 'delete_file', name: 'Delete File', description: 'Remove files', essential: false },
      { id: 'copy_file', name: 'Copy File', description: 'Copy files', essential: false },
      { id: 'move_file', name: 'Move File', description: 'Move/rename files', essential: false },
    ],
  },
  {
    id: 'navigation',
    name: 'Navigation',
    icon: FolderTree,
    color: 'emerald',
    tools: [
      { id: 'list_directory', name: 'List Directory', description: 'Browse directories', essential: true },
      { id: 'find_files', name: 'Find Files', description: 'Search for files', essential: true },
      { id: 'grep_search', name: 'Grep Search', description: 'Search file contents', essential: true },
      { id: 'tree', name: 'Directory Tree', description: 'Show folder structure', essential: false },
    ],
  },
  {
    id: 'git',
    name: 'Git Operations',
    icon: GitBranch,
    color: 'orange',
    tools: [
      { id: 'git_status', name: 'Git Status', description: 'Check repository status', essential: true },
      { id: 'git_diff', name: 'Git Diff', description: 'View changes', essential: true },
      { id: 'git_commit', name: 'Git Commit', description: 'Create commits', essential: true },
      { id: 'git_push', name: 'Git Push', description: 'Push to remote', essential: true },
      { id: 'git_branch', name: 'Git Branch', description: 'Manage branches', essential: false },
      { id: 'git_log', name: 'Git Log', description: 'View history', essential: false },
    ],
  },
  {
    id: 'terminal',
    name: 'Terminal',
    icon: Terminal,
    color: 'purple',
    tools: [
      { id: 'run_command', name: 'Run Command', description: 'Execute shell commands', essential: true, resourceHint: 'high' },
      { id: 'run_script', name: 'Run Script', description: 'Execute scripts', essential: false, resourceHint: 'high' },
      { id: 'run_tests', name: 'Run Tests', description: 'Execute test suites', essential: false, resourceHint: 'medium' },
    ],
  },
  {
    id: 'web',
    name: 'Web & API',
    icon: Globe,
    color: 'blue',
    tools: [
      { id: 'fetch_url', name: 'Fetch URL', description: 'HTTP requests', essential: false, resourceHint: 'medium' },
      { id: 'web_search', name: 'Web Search', description: 'Search the web', essential: false, resourceHint: 'low' },
    ],
  },
  {
    id: 'fastband',
    name: 'Fastband',
    icon: Sparkles,
    color: 'magenta',
    tools: [
      { id: 'ticket_manager', name: 'Ticket Manager', description: 'Create and manage tickets', essential: true },
      { id: 'backup_system', name: 'Backup System', description: 'Create and restore backups', essential: true },
      { id: 'analyze_codebase', name: 'Analyze Codebase', description: 'AI-powered analysis', essential: false, resourceHint: 'high' },
      { id: 'agent_bible', name: 'Agent Bible', description: 'View/edit agent rules', essential: false },
    ],
  },
]

// Get all tool IDs
const allToolIds = toolCategories.flatMap(cat => cat.tools.map(t => t.id))
const essentialToolIds = toolCategories.flatMap(cat =>
  cat.tools.filter(t => t.essential).map(t => t.id)
)

export function ToolsStep({ data, updateData, setStepValid }: StepProps) {
  const [systemInfo, setSystemInfo] = useState({
    ramGB: 16,
    cpuCores: 8,
    aiProvider: 'Claude',
    contextWindow: 200000,
  })

  // Initialize with essential tools if empty
  useEffect(() => {
    if (data.selectedTools.length === 0) {
      updateData({ selectedTools: essentialToolIds })
    }
  }, [])

  // Fetch system capabilities
  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        const response = await fetch('/api/system/capabilities')
        if (response.ok) {
          const info = await response.json()
          setSystemInfo(prev => ({ ...prev, ...info }))
          updateData({ maxRecommendedTools: info.maxRecommendedTools || 40 })
        }
      } catch {
        // Use defaults
      }
    }
    fetchSystemInfo()
  }, [])

  // Always valid - tools are pre-selected
  useEffect(() => {
    setStepValid(data.selectedTools.length > 0)
  }, [data.selectedTools, setStepValid])

  const toggleTool = (toolId: string) => {
    const newSelected = data.selectedTools.includes(toolId)
      ? data.selectedTools.filter(id => id !== toolId)
      : [...data.selectedTools, toolId]
    updateData({ selectedTools: newSelected })
  }

  const selectEssential = () => {
    updateData({ selectedTools: essentialToolIds })
  }

  const selectAll = () => {
    updateData({ selectedTools: allToolIds })
  }

  const isCategoryFullySelected = (category: ToolCategory) => {
    return category.tools.every(t => data.selectedTools.includes(t.id))
  }

  const toggleCategory = (category: ToolCategory) => {
    const categoryToolIds = category.tools.map(t => t.id)
    if (isCategoryFullySelected(category)) {
      // Deselect all in category
      updateData({
        selectedTools: data.selectedTools.filter(id => !categoryToolIds.includes(id)),
      })
    } else {
      // Select all in category
      const newSelected = new Set([...data.selectedTools, ...categoryToolIds])
      updateData({ selectedTools: Array.from(newSelected) })
    }
  }

  return (
    <div className="space-y-5 animate-in">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Select the MCP tools agents can use. Essential tools are pre-selected.
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={selectEssential}
            className="px-3 py-1.5 rounded-lg bg-void-700 text-slate-300 text-xs font-medium hover:bg-void-600 transition-colors"
          >
            Essential Only
          </button>
          <button
            onClick={selectAll}
            className="px-3 py-1.5 rounded-lg bg-cyan/20 text-cyan text-xs font-medium hover:bg-cyan/30 transition-colors"
          >
            Select All
          </button>
        </div>
      </div>

      {/* Performance Meter */}
      <PerformanceMeter
        selectedCount={data.selectedTools.length}
        maxRecommended={data.maxRecommendedTools}
        systemInfo={systemInfo}
      />

      {/* Tool categories */}
      <div className="space-y-4">
        {toolCategories.map(category => {
          const Icon = category.icon
          const selectedInCategory = category.tools.filter(t =>
            data.selectedTools.includes(t.id)
          ).length
          const isFullySelected = isCategoryFullySelected(category)

          return (
            <div
              key={category.id}
              className="rounded-xl border border-void-600/50 overflow-hidden"
            >
              {/* Category header */}
              <button
                onClick={() => toggleCategory(category)}
                className={clsx(
                  'w-full flex items-center justify-between px-4 py-3 transition-colors',
                  isFullySelected
                    ? 'bg-void-700/50 hover:bg-void-700'
                    : 'bg-void-800/30 hover:bg-void-800/50',
                )}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={clsx(
                      'w-8 h-8 rounded-lg flex items-center justify-center',
                      category.color === 'cyan' && 'bg-cyan/10 text-cyan',
                      category.color === 'emerald' && 'bg-emerald-500/10 text-emerald-400',
                      category.color === 'orange' && 'bg-orange-500/10 text-orange-400',
                      category.color === 'purple' && 'bg-purple-500/10 text-purple-400',
                      category.color === 'blue' && 'bg-blue-500/10 text-blue-400',
                      category.color === 'magenta' && 'bg-magenta/10 text-magenta',
                    )}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="text-sm font-medium text-slate-200">
                    {category.name}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">
                    {selectedInCategory}/{category.tools.length}
                  </span>
                  <div
                    className={clsx(
                      'w-5 h-5 rounded border flex items-center justify-center transition-colors',
                      isFullySelected
                        ? 'bg-cyan border-cyan text-void-900'
                        : selectedInCategory > 0
                        ? 'bg-cyan/20 border-cyan/50'
                        : 'border-void-500 bg-void-800',
                    )}
                  >
                    {(isFullySelected || selectedInCategory > 0) && (
                      <Check className="w-3 h-3" />
                    )}
                  </div>
                </div>
              </button>

              {/* Tools grid */}
              <div className="px-4 py-3 bg-void-900/30 grid grid-cols-2 gap-2">
                {category.tools.map(tool => {
                  const isSelected = data.selectedTools.includes(tool.id)

                  return (
                    <button
                      key={tool.id}
                      onClick={() => toggleTool(tool.id)}
                      className={clsx(
                        'flex items-center gap-2 p-2 rounded-lg border text-left transition-all',
                        isSelected
                          ? 'bg-cyan/5 border-cyan/30'
                          : 'bg-void-800/50 border-void-700/50 hover:border-void-600',
                      )}
                    >
                      <div
                        className={clsx(
                          'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors',
                          isSelected
                            ? 'bg-cyan border-cyan text-void-900'
                            : 'border-void-500 bg-void-800',
                        )}
                      >
                        {isSelected && <Check className="w-2.5 h-2.5" />}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={clsx(
                              'text-xs font-medium truncate',
                              isSelected ? 'text-slate-200' : 'text-slate-400',
                            )}
                          >
                            {tool.name}
                          </span>
                          {tool.essential && (
                            <span className="px-1 py-0.5 rounded text-[10px] bg-cyan/20 text-cyan">
                              Core
                            </span>
                          )}
                          {tool.resourceHint === 'high' && (
                            <span className="px-1 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400">
                              Heavy
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-500 truncate">
                          {tool.description}
                        </p>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Summary */}
      <div className="p-4 rounded-xl bg-void-900/50 border border-void-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wrench className="w-4 h-4 text-cyan" />
            <span className="text-sm font-medium text-slate-200">
              {data.selectedTools.length} tools selected
            </span>
          </div>
          {data.selectedTools.length > data.maxRecommendedTools && (
            <div className="flex items-center gap-1.5 text-amber-400 text-xs">
              <Shield className="w-3.5 h-3.5" />
              Consider reducing for better performance
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
