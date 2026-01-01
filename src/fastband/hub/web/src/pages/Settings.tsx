import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  User,
  CreditCard,
  Bell,
  Shield,
  Key,
  Trash2,
  ExternalLink,
  Check,
  Bot,
  Eye,
  EyeOff,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
  Archive,
  FolderOpen,
  Clock,
  Save,
  Folder,
  ChevronRight,
  ArrowUp,
  X,
  Home,
} from 'lucide-react'
import { useAuthStore } from '../stores/auth'
import { useSessionStore } from '../stores/session'
import { Layout } from '../components/Layout'
import { toast } from '../stores/toast'

type Tab = 'profile' | 'ai-providers' | 'backup' | 'billing' | 'notifications' | 'security'

const tabs: { id: Tab; label: string; icon: typeof User }[] = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'ai-providers', label: 'AI Providers', icon: Bot },
  { id: 'backup', label: 'Backup', icon: Archive },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
]

interface ProviderStatus {
  configured: boolean
  valid: boolean | null
  checking: boolean
}

interface ProvidersState {
  anthropic: ProviderStatus
  openai: ProviderStatus
}

const plans = [
  {
    id: 'free',
    name: 'Free',
    price: '$0',
    features: ['100 messages/day', '1GB memory', 'Basic tools', 'Community support'],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '$29',
    features: [
      '5,000 messages/day',
      '50GB memory',
      'All tools',
      'Priority support',
      'Custom integrations',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    features: [
      'Unlimited messages',
      'Unlimited memory',
      'All tools + custom',
      'Dedicated support',
      'SLA guarantee',
      'SSO & audit logs',
    ],
  },
]

export function Settings() {
  const [activeTab, setActiveTab] = useState<Tab>('profile')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // AI Provider state
  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey, setOpenaiKey] = useState('')
  const [showAnthropicKey, setShowAnthropicKey] = useState(false)
  const [showOpenaiKey, setShowOpenaiKey] = useState(false)
  const [providers, setProviders] = useState<ProvidersState>({
    anthropic: { configured: false, valid: null, checking: false },
    openai: { configured: false, valid: null, checking: false },
  })
  const [savingProvider, setSavingProvider] = useState<string | null>(null)

  // Backup settings state
  const [backupPath, setBackupPath] = useState('.fastband/backups')
  const [backupRetentionDays, setBackupRetentionDays] = useState(3)
  const [backupIntervalHours, setBackupIntervalHours] = useState(2)
  const [backupMaxCount, setBackupMaxCount] = useState(50)
  const [loadingBackup, setLoadingBackup] = useState(false)
  const [savingBackup, setSavingBackup] = useState(false)

  // Folder browser state
  const [showFolderBrowser, setShowFolderBrowser] = useState(false)
  const [browserPath, setBrowserPath] = useState('~')
  const [browserEntries, setBrowserEntries] = useState<{ name: string; path: string }[]>([])
  const [browserParent, setBrowserParent] = useState<string | null>(null)
  const [browserLoading, setBrowserLoading] = useState(false)

  const { user, resetOnboarding } = useAuthStore()
  const { tier } = useSessionStore()

  // Check provider status on mount
  useEffect(() => {
    checkProviderStatus()
  }, [])

  // Load backup config on mount
  useEffect(() => {
    loadBackupConfig()
  }, [])

  const loadBackupConfig = async () => {
    setLoadingBackup(true)
    try {
      const response = await fetch('/api/backups/config')
      if (response.ok) {
        const data = await response.json()
        setBackupPath(data.backup_path || '.fastband/backups')
        setBackupRetentionDays(data.retention_days ?? 3)
        setBackupIntervalHours(data.interval_hours ?? 2)
        setBackupMaxCount(data.max_backups ?? 50)
      }
    } catch {
      console.log('Backup config not available')
    } finally {
      setLoadingBackup(false)
    }
  }

  const saveBackupConfig = async () => {
    setSavingBackup(true)
    try {
      const response = await fetch('/api/backups/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          backup_path: backupPath,
          retention_days: backupRetentionDays,
          interval_hours: backupIntervalHours,
          max_backups: backupMaxCount,
        }),
      })

      if (response.ok) {
        toast.success('Backup Settings Saved', 'Your backup configuration has been updated.')
      } else {
        const error = await response.json()
        toast.error('Failed to save', error.detail || 'Please try again')
      }
    } catch {
      toast.error('Connection Error', 'Failed to connect to server')
    } finally {
      setSavingBackup(false)
    }
  }

  const browseFolders = async (path: string) => {
    setBrowserLoading(true)
    try {
      const response = await fetch(`/api/filesystem/browse?path=${encodeURIComponent(path)}`)
      if (response.ok) {
        const data = await response.json()
        setBrowserPath(data.current_path)
        setBrowserParent(data.parent_path)
        setBrowserEntries(data.entries)
      } else {
        const error = await response.json()
        toast.error('Browse Error', error.detail || 'Cannot access folder')
      }
    } catch {
      toast.error('Connection Error', 'Failed to browse filesystem')
    } finally {
      setBrowserLoading(false)
    }
  }

  const openFolderBrowser = async () => {
    // Try native macOS Finder folder picker first
    try {
      const response = await fetch('/api/filesystem/pick-folder', {
        method: 'POST',
      })
      if (response.ok) {
        const data = await response.json()
        setBackupPath(data.path)
        return
      } else if (response.status === 400) {
        // User cancelled - do nothing
        return
      }
      // Fall through to custom browser for other errors
    } catch {
      // Fall back to custom browser
    }
    // Fallback to custom browser
    setShowFolderBrowser(true)
    browseFolders('~')
  }

  const selectFolder = (path: string) => {
    setBackupPath(path)
    setShowFolderBrowser(false)
  }

  const checkProviderStatus = async () => {
    try {
      const response = await fetch('/api/providers/status')
      if (response.ok) {
        const data = await response.json()
        setProviders({
          anthropic: {
            configured: data.anthropic?.configured ?? false,
            valid: data.anthropic?.valid ?? null,
            checking: false
          },
          openai: {
            configured: data.openai?.configured ?? false,
            valid: data.openai?.valid ?? null,
            checking: false
          },
        })
      }
    } catch {
      // API might not exist yet, that's ok
      console.log('Provider status check not available')
    }
  }

  const saveProviderKey = async (provider: 'anthropic' | 'openai', key: string) => {
    if (!key.trim()) return

    setSavingProvider(provider)
    setProviders(prev => ({
      ...prev,
      [provider]: { ...prev[provider], checking: true }
    }))

    try {
      const response = await fetch('/api/providers/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: key }),
      })

      if (response.ok) {
        const data = await response.json()
        setProviders(prev => ({
          ...prev,
          [provider]: { configured: true, valid: data.valid, checking: false }
        }))
        // Clear the input after successful save
        if (provider === 'anthropic') setAnthropicKey('')
        else setOpenaiKey('')
      } else {
        const error = await response.json()
        setProviders(prev => ({
          ...prev,
          [provider]: { configured: false, valid: false, checking: false }
        }))
        toast.error('Failed to save API key', error.detail || 'Please check your key and try again')
      }
    } catch {
      setProviders(prev => ({
        ...prev,
        [provider]: { ...prev[provider], checking: false }
      }))
      toast.error('Connection Error', 'Failed to connect to server')
    } finally {
      setSavingProvider(null)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    // Simulate save
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <Layout>
      <div className="h-full overflow-auto">
        <div className="max-w-4xl mx-auto p-6">
          <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>

          {/* Tabs */}
          <div className="flex gap-2 mb-6 border-b border-gray-700 pb-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                  activeTab === tab.id
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                )}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Profile tab */}
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Profile Information
                </h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      value={user?.email || ''}
                      disabled
                      className={clsx(
                        'w-full px-4 py-3 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-gray-400',
                        'cursor-not-allowed'
                      )}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Email cannot be changed
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      Display Name
                    </label>
                    <input
                      type="text"
                      placeholder="Your name"
                      className={clsx(
                        'w-full px-4 py-3 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-white',
                        'focus:border-blue-500 focus:outline-none'
                      )}
                    />
                  </div>
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className={clsx(
                    'mt-6 flex items-center gap-2 px-4 py-2 rounded-lg',
                    'bg-blue-600 text-white font-medium',
                    'hover:bg-blue-700 transition-colors',
                    'disabled:opacity-50'
                  )}
                >
                  {saved ? (
                    <>
                      <Check className="w-4 h-4" />
                      Saved
                    </>
                  ) : saving ? (
                    'Saving...'
                  ) : (
                    'Save Changes'
                  )}
                </button>
              </div>

              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Danger Zone
                </h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg border border-amber-600/30">
                    <div>
                      <p className="font-medium text-amber-400">Reset Onboarding</p>
                      <p className="text-sm text-gray-400">
                        Re-run the setup wizard on next visit
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        if (confirm('Reset onboarding? You will need to complete the setup wizard again.')) {
                          resetOnboarding()
                          window.location.href = '/'
                        }
                      }}
                      className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg',
                        'bg-amber-600/20 text-amber-400 border border-amber-600/50',
                        'hover:bg-amber-600/30 transition-colors'
                      )}
                    >
                      <RefreshCw className="w-4 h-4" />
                      Reset
                    </button>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg border border-red-600/30">
                    <div>
                      <p className="font-medium text-red-400">Delete Account</p>
                      <p className="text-sm text-gray-400">
                        Permanently delete your account and all data
                      </p>
                    </div>
                    <button
                      className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg',
                        'bg-red-600/20 text-red-400 border border-red-600/50',
                        'hover:bg-red-600/30 transition-colors'
                      )}
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* AI Providers tab */}
          {activeTab === 'ai-providers' && (
            <div className="space-y-6">
              {/* Quick status overview */}
              <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg p-6 border border-blue-500/30">
                <h2 className="text-lg font-semibold text-white mb-2">
                  AI Provider Configuration
                </h2>
                <p className="text-gray-300 text-sm">
                  Configure your AI provider API keys to enable chat and intelligent features.
                  Keys are stored securely and never shared.
                </p>
              </div>

              {/* Anthropic */}
              <div className="bg-gray-800 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                      <Bot className="w-5 h-5 text-orange-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">Anthropic (Claude)</h3>
                      <p className="text-sm text-gray-400">Powers chat and AI assistance</p>
                    </div>
                  </div>
                  {providers.anthropic.configured && (
                    <div className="flex items-center gap-2">
                      {providers.anthropic.valid === true && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs">
                          <CheckCircle className="w-3 h-3" /> Connected
                        </span>
                      )}
                      {providers.anthropic.valid === false && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs">
                          <XCircle className="w-3 h-3" /> Invalid Key
                        </span>
                      )}
                      {providers.anthropic.valid === null && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded bg-yellow-500/20 text-yellow-400 text-xs">
                          <AlertCircle className="w-3 h-3" /> Configured
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <form onSubmit={(e) => { e.preventDefault(); if (anthropicKey.trim()) saveProviderKey('anthropic', anthropicKey); }} className="space-y-3">
                  <div className="relative">
                    <input
                      type={showAnthropicKey ? 'text' : 'password'}
                      value={anthropicKey}
                      onChange={(e) => setAnthropicKey(e.target.value)}
                      placeholder={providers.anthropic.configured ? '••••••••••••••••' : 'sk-ant-...'}
                      aria-label="Anthropic API key"
                      autoComplete="off"
                      className={clsx(
                        'w-full px-4 py-3 pr-20 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-white',
                        'focus:border-blue-500 focus:outline-none',
                        'placeholder:text-gray-500'
                      )}
                    />
                    <button
                      type="button"
                      onClick={() => setShowAnthropicKey(!showAnthropicKey)}
                      aria-label={showAnthropicKey ? 'Hide Anthropic API key' : 'Show Anthropic API key'}
                      aria-pressed={showAnthropicKey}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                    >
                      {showAnthropicKey ? <EyeOff className="w-5 h-5" aria-hidden="true" /> : <Eye className="w-5 h-5" aria-hidden="true" />}
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <a
                      href="https://console.anthropic.com/settings/keys"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      Get an API key <ExternalLink className="w-3 h-3" />
                    </a>
                    <button
                      type="submit"
                      disabled={!anthropicKey.trim() || savingProvider === 'anthropic'}
                      className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg',
                        'bg-blue-600 text-white font-medium',
                        'hover:bg-blue-700 transition-colors',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                    >
                      {savingProvider === 'anthropic' ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Key className="w-4 h-4" />
                          Save Key
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              {/* OpenAI */}
              <div className="bg-gray-800 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                      <Bot className="w-5 h-5 text-green-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">OpenAI</h3>
                      <p className="text-sm text-gray-400">Powers embeddings and semantic search</p>
                    </div>
                  </div>
                  {providers.openai.configured && (
                    <div className="flex items-center gap-2">
                      {providers.openai.valid === true && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs">
                          <CheckCircle className="w-3 h-3" /> Connected
                        </span>
                      )}
                      {providers.openai.valid === false && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs">
                          <XCircle className="w-3 h-3" /> Invalid Key
                        </span>
                      )}
                      {providers.openai.valid === null && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded bg-yellow-500/20 text-yellow-400 text-xs">
                          <AlertCircle className="w-3 h-3" /> Configured
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <form onSubmit={(e) => { e.preventDefault(); if (openaiKey.trim()) saveProviderKey('openai', openaiKey); }} className="space-y-3">
                  <div className="relative">
                    <input
                      type={showOpenaiKey ? 'text' : 'password'}
                      value={openaiKey}
                      onChange={(e) => setOpenaiKey(e.target.value)}
                      placeholder={providers.openai.configured ? '••••••••••••••••' : 'sk-...'}
                      aria-label="OpenAI API key"
                      autoComplete="off"
                      className={clsx(
                        'w-full px-4 py-3 pr-20 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-white',
                        'focus:border-blue-500 focus:outline-none',
                        'placeholder:text-gray-500'
                      )}
                    />
                    <button
                      type="button"
                      onClick={() => setShowOpenaiKey(!showOpenaiKey)}
                      aria-label={showOpenaiKey ? 'Hide OpenAI API key' : 'Show OpenAI API key'}
                      aria-pressed={showOpenaiKey}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                    >
                      {showOpenaiKey ? <EyeOff className="w-5 h-5" aria-hidden="true" /> : <Eye className="w-5 h-5" aria-hidden="true" />}
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <a
                      href="https://platform.openai.com/api-keys"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      Get an API key <ExternalLink className="w-3 h-3" />
                    </a>
                    <button
                      type="submit"
                      disabled={!openaiKey.trim() || savingProvider === 'openai'}
                      className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg',
                        'bg-blue-600 text-white font-medium',
                        'hover:bg-blue-700 transition-colors',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                    >
                      {savingProvider === 'openai' ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Key className="w-4 h-4" />
                          Save Key
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              {/* Help text */}
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <h4 className="text-sm font-medium text-gray-300 mb-2">
                  Alternatively, set via environment variables:
                </h4>
                <pre className="text-xs text-gray-400 bg-gray-900 p-3 rounded overflow-x-auto">
{`export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...`}
                </pre>
              </div>
            </div>
          )}

          {/* Backup tab */}
          {activeTab === 'backup' && (
            <div className="space-y-6">
              {/* Overview */}
              <div className="bg-gradient-to-r from-cyan-900/50 to-blue-900/50 rounded-lg p-6 border border-cyan-500/30">
                <h2 className="text-lg font-semibold text-white mb-2">
                  Backup Configuration
                </h2>
                <p className="text-gray-300 text-sm">
                  Configure where backups are stored and how long they're retained.
                  Backups include your database, configuration, and ticket history.
                </p>
              </div>

              {/* Storage Location */}
              <div className="bg-gray-800 rounded-lg p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                    <FolderOpen className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">Storage Location</h3>
                    <p className="text-sm text-gray-400">Where backups are saved</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      Backup Path
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={backupPath}
                        onChange={(e) => setBackupPath(e.target.value)}
                        placeholder=".fastband/backups"
                        disabled={loadingBackup}
                        className={clsx(
                          'flex-1 px-4 py-3 rounded-lg',
                          'bg-gray-700 border border-gray-600 text-white',
                          'focus:border-cyan-500 focus:outline-none',
                          'placeholder:text-gray-500',
                          'disabled:opacity-50'
                        )}
                      />
                      <button
                        type="button"
                        onClick={openFolderBrowser}
                        disabled={loadingBackup}
                        className={clsx(
                          'px-4 py-3 rounded-lg',
                          'bg-cyan-600/20 border border-cyan-500/50 text-cyan-400',
                          'hover:bg-cyan-600/30 transition-colors',
                          'disabled:opacity-50 disabled:cursor-not-allowed',
                          'flex items-center gap-2'
                        )}
                      >
                        <FolderOpen className="w-5 h-5" />
                        Browse
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Relative to project root, or use an absolute path like /Volumes/backup/fastband
                    </p>
                  </div>
                </div>
              </div>

              {/* Retention Settings */}
              <div className="bg-gray-800 rounded-lg p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                    <Clock className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">Retention Settings</h3>
                    <p className="text-sm text-gray-400">How long to keep backups</p>
                  </div>
                </div>

                <div className="grid md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      Retention Days
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={backupRetentionDays}
                      onChange={(e) => setBackupRetentionDays(Number(e.target.value))}
                      disabled={loadingBackup}
                      className={clsx(
                        'w-full px-4 py-3 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-white',
                        'focus:border-purple-500 focus:outline-none',
                        'disabled:opacity-50'
                      )}
                    />
                    <p className="text-xs text-gray-500 mt-1">Days to keep backups</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      Backup Interval
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={24}
                      value={backupIntervalHours}
                      onChange={(e) => setBackupIntervalHours(Number(e.target.value))}
                      disabled={loadingBackup}
                      className={clsx(
                        'w-full px-4 py-3 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-white',
                        'focus:border-purple-500 focus:outline-none',
                        'disabled:opacity-50'
                      )}
                    />
                    <p className="text-xs text-gray-500 mt-1">Hours between backups</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      Max Backups
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      value={backupMaxCount}
                      onChange={(e) => setBackupMaxCount(Number(e.target.value))}
                      disabled={loadingBackup}
                      className={clsx(
                        'w-full px-4 py-3 rounded-lg',
                        'bg-gray-700 border border-gray-600 text-white',
                        'focus:border-purple-500 focus:outline-none',
                        'disabled:opacity-50'
                      )}
                    />
                    <p className="text-xs text-gray-500 mt-1">Total backups to keep</p>
                  </div>
                </div>
              </div>

              {/* Save Button */}
              <div className="flex justify-end">
                <button
                  onClick={saveBackupConfig}
                  disabled={savingBackup || loadingBackup}
                  className={clsx(
                    'flex items-center gap-2 px-6 py-3 rounded-lg',
                    'bg-cyan-600 text-white font-medium',
                    'hover:bg-cyan-700 transition-colors',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  {savingBackup ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" />
                      Save Backup Settings
                    </>
                  )}
                </button>
              </div>

              {/* Current backup info */}
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <h4 className="text-sm font-medium text-gray-300 mb-2">
                  Current Configuration
                </h4>
                <pre className="text-xs text-gray-400 bg-gray-900 p-3 rounded overflow-x-auto">
{`# Backup settings in .fastband/config.yaml
backup:
  backup_path: "${backupPath}"
  retention_days: ${backupRetentionDays}
  interval_hours: ${backupIntervalHours}
  max_backups: ${backupMaxCount}`}
                </pre>
              </div>
            </div>
          )}

          {/* Billing tab */}
          {activeTab === 'billing' && (
            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Current Plan
                </h2>
                <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                  <div>
                    <p className="font-medium text-white capitalize">{tier} Plan</p>
                    <p className="text-sm text-gray-400">
                      {tier === 'free' && 'Basic access with limited features'}
                      {tier === 'pro' && 'Full access to all features'}
                      {tier === 'enterprise' && 'Custom enterprise solution'}
                    </p>
                  </div>
                  <button
                    className={clsx(
                      'flex items-center gap-2 px-4 py-2 rounded-lg',
                      'bg-blue-600 text-white font-medium',
                      'hover:bg-blue-700 transition-colors'
                    )}
                  >
                    Manage Subscription
                    <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Available Plans
                </h2>
                <div className="grid md:grid-cols-3 gap-4">
                  {plans.map((plan) => (
                    <div
                      key={plan.id}
                      className={clsx(
                        'p-4 rounded-lg border-2 transition-colors',
                        tier === plan.id
                          ? 'border-blue-500 bg-blue-500/10'
                          : 'border-gray-700'
                      )}
                    >
                      <h3 className="font-semibold text-white">{plan.name}</h3>
                      <p className="text-2xl font-bold text-white mt-1">
                        {plan.price}
                        {plan.id !== 'enterprise' && (
                          <span className="text-sm text-gray-400 font-normal">
                            /month
                          </span>
                        )}
                      </p>
                      <ul className="mt-4 space-y-2">
                        {plan.features.map((feature, i) => (
                          <li
                            key={i}
                            className="flex items-center gap-2 text-sm text-gray-300"
                          >
                            <Check className="w-4 h-4 text-green-400" />
                            {feature}
                          </li>
                        ))}
                      </ul>
                      {tier !== plan.id && (
                        <button
                          className={clsx(
                            'w-full mt-4 px-4 py-2 rounded-lg font-medium transition-colors',
                            plan.id === 'enterprise'
                              ? 'bg-purple-600 text-white hover:bg-purple-700'
                              : 'bg-blue-600 text-white hover:bg-blue-700'
                          )}
                        >
                          {plan.id === 'enterprise' ? 'Contact Sales' : 'Upgrade'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Notifications tab */}
          {activeTab === 'notifications' && (
            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">
                Notification Preferences
              </h2>

              <div className="space-y-4">
                {[
                  {
                    id: 'email_updates',
                    label: 'Email Updates',
                    desc: 'Receive product updates and announcements',
                  },
                  {
                    id: 'usage_alerts',
                    label: 'Usage Alerts',
                    desc: 'Get notified when approaching usage limits',
                  },
                  {
                    id: 'security_alerts',
                    label: 'Security Alerts',
                    desc: 'Important security notifications',
                  },
                ].map((item) => (
                  <label
                    key={item.id}
                    className="flex items-center justify-between p-4 bg-gray-700 rounded-lg cursor-pointer"
                  >
                    <div>
                      <p className="font-medium text-white">{item.label}</p>
                      <p className="text-sm text-gray-400">{item.desc}</p>
                    </div>
                    <input
                      type="checkbox"
                      defaultChecked
                      className="w-5 h-5 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Security tab */}
          {activeTab === 'security' && (
            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  API Keys
                </h2>
                <p className="text-gray-400 mb-4">
                  Manage API keys for programmatic access to Fastband services.
                </p>
                <button
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg',
                    'bg-blue-600 text-white font-medium',
                    'hover:bg-blue-700 transition-colors'
                  )}
                >
                  <Key className="w-4 h-4" />
                  Generate New API Key
                </button>
              </div>

              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Active Sessions
                </h2>
                <p className="text-gray-400 mb-4">
                  View and manage your active login sessions.
                </p>
                <div className="p-4 bg-gray-700 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-white">Current Session</p>
                      <p className="text-sm text-gray-400">
                        {navigator.userAgent.split(' ').slice(0, 3).join(' ')}
                      </p>
                    </div>
                    <span className="px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs">
                      Active
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Folder Browser Modal */}
      {showFolderBrowser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
              <h3 className="text-lg font-semibold text-white">Select Backup Folder</h3>
              <button
                onClick={() => setShowFolderBrowser(false)}
                className="p-2 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Current Path */}
            <div className="px-6 py-3 bg-gray-800/50 border-b border-gray-700 flex items-center gap-2">
              <button
                onClick={() => browseFolders('~')}
                className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-cyan-400 transition-colors"
                title="Home"
              >
                <Home className="w-4 h-4" />
              </button>
              {browserParent && (
                <button
                  onClick={() => browseFolders(browserParent)}
                  className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-cyan-400 transition-colors"
                  title="Go up"
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              )}
              <div className="flex-1 px-3 py-1.5 bg-gray-700 rounded text-sm text-gray-300 font-mono truncate">
                {browserPath}
              </div>
            </div>

            {/* Folder List */}
            <div className="flex-1 overflow-y-auto p-2">
              {browserLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
                </div>
              ) : browserEntries.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  No subfolders found
                </div>
              ) : (
                <div className="space-y-1">
                  {browserEntries.map((entry) => (
                    <button
                      key={entry.path}
                      onClick={() => browseFolders(entry.path)}
                      className={clsx(
                        'w-full flex items-center gap-3 px-4 py-2.5 rounded-lg',
                        'hover:bg-gray-700/50 transition-colors text-left group'
                      )}
                    >
                      <Folder className="w-5 h-5 text-cyan-400" />
                      <span className="flex-1 text-gray-200">{entry.name}</span>
                      <ChevronRight className="w-4 h-4 text-gray-500 group-hover:text-gray-300" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-gray-700 bg-gray-800/50">
              <p className="text-sm text-gray-400">
                Select a folder or navigate to create a new one
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowFolderBrowser(false)}
                  className="px-4 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => selectFolder(browserPath)}
                  className={clsx(
                    'px-4 py-2 rounded-lg font-medium',
                    'bg-cyan-600 text-white hover:bg-cyan-700 transition-colors',
                    'flex items-center gap-2'
                  )}
                >
                  <Check className="w-4 h-4" />
                  Select This Folder
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
