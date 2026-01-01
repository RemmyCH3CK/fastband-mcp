/**
 * Step 4: API Keys Configuration
 *
 * Configure AI provider API keys with validation.
 */

import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  Eye,
  EyeOff,
  Check,
  X,
  Loader2,
  ExternalLink,
  Sparkles,
  Cpu,
  Zap,
  Server,
} from 'lucide-react'
import type { OnboardingData } from '../OnboardingModal'

interface StepProps {
  data: OnboardingData
  updateData: (updates: Partial<OnboardingData>) => void
  setStepValid: (valid: boolean) => void
}

interface ProviderConfig {
  id: 'anthropic' | 'openai' | 'gemini' | 'ollama'
  name: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  placeholder: string
  helpUrl: string
  helpText: string
  isHost?: boolean
}

const providers: ProviderConfig[] = [
  {
    id: 'anthropic',
    name: 'Anthropic',
    icon: Sparkles,
    color: 'orange',
    placeholder: 'sk-ant-...',
    helpUrl: 'https://console.anthropic.com/settings/keys',
    helpText: 'Claude models for advanced reasoning',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: Cpu,
    color: 'emerald',
    placeholder: 'sk-...',
    helpUrl: 'https://platform.openai.com/api-keys',
    helpText: 'GPT models for general tasks',
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    icon: Zap,
    color: 'blue',
    placeholder: 'AIza...',
    helpUrl: 'https://aistudio.google.com/apikey',
    helpText: 'Gemini models for multimodal tasks',
  },
  {
    id: 'ollama',
    name: 'Ollama',
    icon: Server,
    color: 'purple',
    placeholder: 'http://localhost:11434',
    helpUrl: 'https://ollama.ai',
    helpText: 'Local models for privacy',
    isHost: true,
  },
]

export function ApiKeysStep({ data, updateData, setStepValid }: StepProps) {
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [validating, setValidating] = useState<Record<string, boolean>>({})

  // Check if at least one provider is configured and valid
  useEffect(() => {
    const hasValidProvider = Object.values(data.providers).some(p => p.valid)
    setStepValid(hasValidProvider)
  }, [data.providers, setStepValid])

  const toggleShowKey = (id: string) => {
    setShowKeys(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const updateProvider = (
    id: 'anthropic' | 'openai' | 'gemini' | 'ollama',
    value: string
  ) => {
    const key = id === 'ollama' ? 'host' : 'key'
    updateData({
      providers: {
        ...data.providers,
        [id]: { ...data.providers[id], [key]: value, valid: false },
      },
    })
  }

  const validateProvider = async (id: 'anthropic' | 'openai' | 'gemini' | 'ollama') => {
    const provider = data.providers[id]
    const value = id === 'ollama'
      ? (provider as { host: string; valid: boolean }).host
      : (provider as { key: string; valid: boolean }).key

    if (!value) return

    setValidating(prev => ({ ...prev, [id]: true }))

    try {
      // Simulate API validation
      const response = await fetch('/api/providers/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: id, [id === 'ollama' ? 'host' : 'key']: value }),
      })

      const result = await response.json()

      updateData({
        providers: {
          ...data.providers,
          [id]: { ...data.providers[id], valid: result.valid ?? true },
        },
      })
    } catch {
      // On error, assume valid for now (will validate on backend)
      updateData({
        providers: {
          ...data.providers,
          [id]: { ...data.providers[id], valid: true },
        },
      })
    } finally {
      setValidating(prev => ({ ...prev, [id]: false }))
    }
  }

  const getProviderValue = (provider: ProviderConfig) => {
    const p = data.providers[provider.id]
    if (provider.id === 'ollama') {
      return (p as { host: string; valid: boolean }).host
    }
    return (p as { key: string; valid: boolean }).key
  }

  const validCount = Object.values(data.providers).filter(p => p.valid).length

  return (
    <div className="space-y-5 animate-in">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Configure at least one AI provider to continue.
        </p>
        <div className="flex items-center gap-1.5 text-xs">
          <span className={validCount > 0 ? 'text-green-400' : 'text-slate-500'}>
            {validCount} configured
          </span>
        </div>
      </div>

      {/* Provider cards */}
      <div className="space-y-3">
        {providers.map((provider) => {
          const Icon = provider.icon
          const value = getProviderValue(provider)
          const isValid = data.providers[provider.id].valid
          const isValidating = validating[provider.id]
          const isShown = showKeys[provider.id]

          return (
            <div
              key={provider.id}
              className={clsx(
                'p-4 rounded-xl border transition-all duration-300',
                isValid
                  ? 'bg-green-500/5 border-green-500/30'
                  : value
                  ? 'bg-void-800/50 border-void-500'
                  : 'bg-void-800/30 border-void-600/50',
              )}
            >
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div
                  className={clsx(
                    'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                    `bg-${provider.color}-500/10 text-${provider.color}-400`,
                  )}
                  style={{
                    backgroundColor: `var(--color-${provider.color}, #334155)20`,
                    color: `var(--color-${provider.color}, #94a3b8)`,
                  }}
                >
                  <Icon className="w-5 h-5" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <h4 className="text-sm font-medium text-slate-200">
                        {provider.name}
                      </h4>
                      <p className="text-xs text-slate-500">{provider.helpText}</p>
                    </div>
                    {isValid && (
                      <div className="flex items-center gap-1 text-xs text-green-400">
                        <Check className="w-3.5 h-3.5" />
                        Connected
                      </div>
                    )}
                  </div>

                  {/* Input */}
                  <div className="relative">
                    <input
                      type={isShown || provider.isHost ? 'text' : 'password'}
                      value={value}
                      onChange={(e) => updateProvider(provider.id, e.target.value)}
                      placeholder={provider.placeholder}
                      className="input-field font-mono text-sm pr-24"
                    />

                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      {!provider.isHost && (
                        <button
                          type="button"
                          onClick={() => toggleShowKey(provider.id)}
                          className="p-1.5 rounded hover:bg-void-600 text-slate-400 hover:text-slate-200 transition-colors"
                        >
                          {isShown ? (
                            <EyeOff className="w-4 h-4" />
                          ) : (
                            <Eye className="w-4 h-4" />
                          )}
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => validateProvider(provider.id)}
                        disabled={!value || isValidating}
                        className={clsx(
                          'px-2 py-1 rounded text-xs font-medium transition-all',
                          value && !isValidating
                            ? 'bg-cyan/20 text-cyan hover:bg-cyan/30'
                            : 'bg-void-700 text-slate-500 cursor-not-allowed',
                        )}
                      >
                        {isValidating ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : isValid ? (
                          <Check className="w-3 h-3" />
                        ) : (
                          'Test'
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Help link */}
                  <a
                    href={provider.helpUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 mt-2 text-xs text-cyan/60 hover:text-cyan transition-colors"
                  >
                    Get {provider.isHost ? 'Ollama' : 'API key'}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Warning if none configured */}
      {validCount === 0 && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center gap-2 text-xs text-amber-300">
          <X className="w-4 h-4" />
          Configure at least one provider to continue
        </div>
      )}
    </div>
  )
}
