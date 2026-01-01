/**
 * Agent Bible Editor Page
 *
 * View and edit the AGENT_BIBLE.md file with structured rules support.
 */

import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  BookOpen,
  Save,
  RefreshCw,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Shield,
  Code,
  TestTube,
  GitBranch,
  Settings,
  Loader2,
} from 'lucide-react'
import { Layout } from '../components/Layout'

interface BibleRule {
  id: string
  category: string
  severity: 'MUST' | 'SHOULD' | 'MAY' | 'MUST_NOT'
  description: string
}

const CATEGORIES = [
  { id: 'security', name: 'Security', icon: Shield, color: 'red' },
  { id: 'code_style', name: 'Code Style', icon: Code, color: 'blue' },
  { id: 'testing', name: 'Testing', icon: TestTube, color: 'green' },
  { id: 'workflow', name: 'Workflow', icon: GitBranch, color: 'purple' },
  { id: 'architecture', name: 'Architecture', icon: Settings, color: 'orange' },
  { id: 'custom', name: 'Custom', icon: Sparkles, color: 'cyan' },
]

const SEVERITIES = [
  { id: 'MUST', label: 'MUST', color: 'red', description: 'Required - agents must always follow' },
  { id: 'SHOULD', label: 'SHOULD', color: 'yellow', description: 'Recommended - follow unless good reason not to' },
  { id: 'MAY', label: 'MAY', color: 'green', description: 'Optional - agents can choose' },
  { id: 'MUST_NOT', label: 'MUST NOT', color: 'red', description: 'Prohibited - agents must never do this' },
]

export function BibleEditor() {
  const [content, setContent] = useState('')
  const [rules, setRules] = useState<BibleRule[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showRawEditor, setShowRawEditor] = useState(false)
  const [newRule, setNewRule] = useState<Partial<BibleRule>>({
    category: 'custom',
    severity: 'SHOULD',
    description: '',
  })
  const [showNewRuleForm, setShowNewRuleForm] = useState(false)

  // Load Bible content
  useEffect(() => {
    loadBible()
  }, [])

  const loadBible = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/bible')
      const data = await response.json()

      if (data.exists) {
        setContent(data.content)
        // Parse rules from content
        const parsedRules = parseRulesFromContent(data.content)
        setRules(parsedRules)
      }
    } catch (err) {
      setError('Failed to load Agent Bible')
    } finally {
      setLoading(false)
    }
  }

  const parseRulesFromContent = (content: string): BibleRule[] => {
    const rules: BibleRule[] = []
    const tableMatch = content.match(/\|.*\|.*\|.*\|[\s\S]*?(?=\n\n|<!-- END)/g)

    if (tableMatch) {
      const lines = tableMatch[0].split('\n').filter(line =>
        line.startsWith('|') && !line.includes('---') && !line.includes('Severity')
      )

      lines.forEach((line, index) => {
        const cells = line.split('|').filter(c => c.trim())
        if (cells.length >= 3) {
          rules.push({
            id: `rule-${index}`,
            severity: cells[0].trim() as BibleRule['severity'],
            category: cells[1].trim(),
            description: cells[2].trim(),
          })
        }
      })
    }

    return rules
  }

  const saveBible = async () => {
    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch('/api/bible', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })

      if (response.ok) {
        setSuccess('Agent Bible saved successfully')
        setTimeout(() => setSuccess(null), 3000)
      } else {
        throw new Error('Failed to save')
      }
    } catch (err) {
      setError('Failed to save Agent Bible')
    } finally {
      setSaving(false)
    }
  }

  const regenerateBible = async () => {
    setRegenerating(true)
    setError(null)

    try {
      const response = await fetch('/api/analyze/generate-bible', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ regenerate: true }),
      })

      const data = await response.json()
      if (data.success) {
        setContent(data.content)
        setRules(parseRulesFromContent(data.content))
        setSuccess('Agent Bible regenerated')
        setTimeout(() => setSuccess(null), 3000)
      }
    } catch (err) {
      setError('Failed to regenerate Agent Bible')
    } finally {
      setRegenerating(false)
    }
  }

  const addRule = async () => {
    if (!newRule.description?.trim()) return

    try {
      const response = await fetch('/api/bible/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRule),
      })

      if (response.ok) {
        // Reload to get updated content
        await loadBible()
        setNewRule({ category: 'custom', severity: 'SHOULD', description: '' })
        setShowNewRuleForm(false)
        setSuccess('Rule added successfully')
        setTimeout(() => setSuccess(null), 3000)
      }
    } catch (err) {
      setError('Failed to add rule')
    }
  }

  const deleteRule = (index: number) => {
    const newRules = [...rules]
    newRules.splice(index, 1)
    setRules(newRules)

    // Rebuild content with updated rules
    rebuildContent(newRules)
  }

  const rebuildContent = (updatedRules: BibleRule[]) => {
    // Build new rules table
    const rulesTable = `<!-- BEGIN_STRUCTURED_RULES -->
| Severity | Category | Rule |
|----------|----------|------|
${updatedRules.map(r => `| ${r.severity} | ${r.category} | ${r.description} |`).join('\n')}
<!-- END_STRUCTURED_RULES -->`

    // Replace rules section in content
    const newContent = content.replace(
      /<!-- BEGIN_STRUCTURED_RULES -->[\s\S]*?<!-- END_STRUCTURED_RULES -->/,
      rulesTable
    )

    setContent(newContent)
  }

  const getCategoryIcon = (categoryId: string) => {
    const category = CATEGORIES.find(c => c.id === categoryId)
    return category?.icon || Sparkles
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'MUST':
      case 'MUST_NOT':
        return 'text-red-400 bg-red-500/10 border-red-500/30'
      case 'SHOULD':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/30'
      case 'MAY':
        return 'text-green-400 bg-green-500/10 border-green-500/30'
      default:
        return 'text-slate-400 bg-slate-500/10 border-slate-500/30'
    }
  }

  if (loading) {
    return (
      <Layout showConversationSidebar={false}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 text-cyan animate-spin" />
        </div>
      </Layout>
    )
  }

  return (
    <Layout showConversationSidebar={false}>
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-magenta/20 to-cyan/20 border border-magenta/30 flex items-center justify-center">
              <BookOpen className="w-6 h-6 text-magenta" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-slate-100">
                Agent Bible
              </h1>
              <p className="text-sm text-slate-400">
                Define rules and guidelines for AI agents
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={regenerateBible}
              disabled={regenerating}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-void-700 text-slate-300 hover:bg-void-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={clsx('w-4 h-4', regenerating && 'animate-spin')} />
              Regenerate
            </button>
            <button
              onClick={saveBible}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan text-void-900 font-medium hover:shadow-glow-cyan transition-all disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Changes
            </button>
          </div>
        </div>

        {/* Notifications */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <span className="text-red-300">{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 rounded-xl bg-green-500/10 border border-green-500/30 flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="text-green-300">{success}</span>
          </div>
        )}

        {/* Rules Section */}
        <div className="rounded-xl bg-void-800/50 border border-void-600/50 overflow-hidden mb-6">
          <div className="flex items-center justify-between px-6 py-4 border-b border-void-600/50">
            <h2 className="text-lg font-semibold text-slate-100">Agent Laws</h2>
            <button
              onClick={() => setShowNewRuleForm(!showNewRuleForm)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-magenta/20 text-magenta text-sm font-medium hover:bg-magenta/30 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Rule
            </button>
          </div>

          {/* New Rule Form */}
          {showNewRuleForm && (
            <div className="px-6 py-4 bg-magenta/5 border-b border-magenta/20">
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Severity</label>
                  <select
                    value={newRule.severity}
                    onChange={(e) => setNewRule({ ...newRule, severity: e.target.value as BibleRule['severity'] })}
                    className="w-full px-3 py-2 rounded-lg bg-void-800 border border-void-600 text-slate-200 text-sm"
                  >
                    {SEVERITIES.map(s => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Category</label>
                  <select
                    value={newRule.category}
                    onChange={(e) => setNewRule({ ...newRule, category: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-void-800 border border-void-600 text-slate-200 text-sm"
                  >
                    {CATEGORIES.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div className="col-span-1">
                  <label className="block text-xs text-slate-400 mb-1">&nbsp;</label>
                  <button
                    onClick={addRule}
                    disabled={!newRule.description?.trim()}
                    className="w-full px-3 py-2 rounded-lg bg-magenta text-void-900 font-medium text-sm hover:shadow-glow-magenta transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Add Rule
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Rule Description</label>
                <input
                  type="text"
                  value={newRule.description}
                  onChange={(e) => setNewRule({ ...newRule, description: e.target.value })}
                  placeholder="Enter rule description..."
                  className="w-full px-3 py-2 rounded-lg bg-void-800 border border-void-600 text-slate-200 text-sm placeholder:text-slate-500"
                />
              </div>
            </div>
          )}

          {/* Rules List */}
          <div className="divide-y divide-void-700/50">
            {rules.length === 0 ? (
              <div className="px-6 py-8 text-center text-slate-500">
                No rules defined. Add your first rule above.
              </div>
            ) : (
              rules.map((rule, index) => {
                const CategoryIcon = getCategoryIcon(rule.category)
                return (
                  <div
                    key={rule.id}
                    className="flex items-center gap-4 px-6 py-4 hover:bg-void-700/30 transition-colors"
                  >
                    <span
                      className={clsx(
                        'px-2 py-1 rounded text-xs font-mono font-bold border',
                        getSeverityColor(rule.severity)
                      )}
                    >
                      {rule.severity}
                    </span>
                    <div className="flex items-center gap-2 w-32">
                      <CategoryIcon className="w-4 h-4 text-slate-500" />
                      <span className="text-sm text-slate-400">{rule.category}</span>
                    </div>
                    <span className="flex-1 text-sm text-slate-200">{rule.description}</span>
                    <button
                      onClick={() => deleteRule(index)}
                      className="p-2 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Raw Editor Toggle */}
        <button
          onClick={() => setShowRawEditor(!showRawEditor)}
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors mb-4"
        >
          {showRawEditor ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          {showRawEditor ? 'Hide' : 'Show'} Raw Markdown Editor
        </button>

        {/* Raw Markdown Editor */}
        {showRawEditor && (
          <div className="rounded-xl bg-void-800/50 border border-void-600/50 overflow-hidden">
            <div className="px-6 py-4 border-b border-void-600/50">
              <h2 className="text-lg font-semibold text-slate-100">Raw Markdown</h2>
              <p className="text-sm text-slate-400 mt-1">
                Edit the full AGENT_BIBLE.md content directly
              </p>
            </div>
            <div className="p-4">
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full h-96 px-4 py-3 rounded-lg bg-void-900 border border-void-700 text-slate-200 font-mono text-sm resize-none focus:outline-none focus:border-cyan/50"
                placeholder="# Agent Bible&#10;&#10;Your rules here..."
              />
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
