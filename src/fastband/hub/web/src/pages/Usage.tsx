import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import {
  MessageSquare,
  Cpu,
  HardDrive,
  TrendingUp,
  Calendar,
  Loader2,
} from 'lucide-react'
import { Layout } from '../components/Layout'
import { useSessionStore } from '../stores/session'

interface UsageData {
  period: string
  messages_used: number
  messages_limit: number
  tokens_used: number
  tokens_limit: number
  memory_used_mb: number
  memory_limit_mb: number
  daily_usage: Array<{
    date: string
    messages: number
    tokens: number
  }>
}

export function Usage() {
  const [loading, setLoading] = useState(true)
  const [usage, setUsage] = useState<UsageData | null>(null)
  const { tier, sessionId } = useSessionStore()

  useEffect(() => {
    async function fetchUsage() {
      try {
        const response = await fetch(`/api/usage?session_id=${sessionId}`)
        if (response.ok) {
          const data = await response.json()
          setUsage(data)
        }
      } catch (err) {
        console.error('Failed to fetch usage:', err)
      } finally {
        setLoading(false)
      }
    }

    if (sessionId) {
      fetchUsage()
    }
  }, [sessionId])

  // Mock data for demo
  const mockUsage: UsageData = {
    period: 'December 2024',
    messages_used: 847,
    messages_limit: tier === 'free' ? 100 : tier === 'pro' ? 5000 : 999999,
    tokens_used: 1250000,
    tokens_limit: tier === 'free' ? 100000 : tier === 'pro' ? 5000000 : 999999999,
    memory_used_mb: 256,
    memory_limit_mb: tier === 'free' ? 1024 : tier === 'pro' ? 51200 : 999999,
    daily_usage: [
      { date: '2024-12-22', messages: 45, tokens: 67500 },
      { date: '2024-12-23', messages: 78, tokens: 117000 },
      { date: '2024-12-24', messages: 123, tokens: 184500 },
      { date: '2024-12-25', messages: 89, tokens: 133500 },
      { date: '2024-12-26', messages: 156, tokens: 234000 },
      { date: '2024-12-27', messages: 201, tokens: 301500 },
      { date: '2024-12-28', messages: 155, tokens: 232500 },
    ],
  }

  const data = usage || mockUsage

  const getPercentage = (used: number, limit: number) => {
    if (limit === 999999 || limit === 999999999) return 5 // Show minimal for unlimited
    return Math.min((used / limit) * 100, 100)
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const getBarColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500'
    if (percentage >= 75) return 'bg-yellow-500'
    return 'bg-blue-500'
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-full">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      </Layout>
    )
  }

  const maxMessages = Math.max(...data.daily_usage.map((d) => d.messages))

  return (
    <Layout>
      <div className="h-full overflow-auto">
        <div className="max-w-4xl mx-auto p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-white">Usage Statistics</h1>
              <p className="text-gray-400">Track your API usage and limits</p>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <Calendar className="w-4 h-4" />
              {data.period}
            </div>
          </div>

          {/* Usage Cards */}
          <div className="grid md:grid-cols-3 gap-4 mb-8">
            {/* Messages */}
            <div className="bg-gray-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-sm text-gray-400">Messages</p>
                  <p className="text-xl font-bold text-white">
                    {formatNumber(data.messages_used)}
                    <span className="text-sm text-gray-400 font-normal">
                      {data.messages_limit < 999999
                        ? ` / ${formatNumber(data.messages_limit)}`
                        : ' (unlimited)'}
                    </span>
                  </p>
                </div>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    getBarColor(getPercentage(data.messages_used, data.messages_limit))
                  )}
                  style={{
                    width: `${getPercentage(data.messages_used, data.messages_limit)}%`,
                  }}
                />
              </div>
            </div>

            {/* Tokens */}
            <div className="bg-gray-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <p className="text-sm text-gray-400">Tokens</p>
                  <p className="text-xl font-bold text-white">
                    {formatNumber(data.tokens_used)}
                    <span className="text-sm text-gray-400 font-normal">
                      {data.tokens_limit < 999999999
                        ? ` / ${formatNumber(data.tokens_limit)}`
                        : ' (unlimited)'}
                    </span>
                  </p>
                </div>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    getBarColor(getPercentage(data.tokens_used, data.tokens_limit))
                  )}
                  style={{
                    width: `${getPercentage(data.tokens_used, data.tokens_limit)}%`,
                  }}
                />
              </div>
            </div>

            {/* Memory */}
            <div className="bg-gray-800 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                  <HardDrive className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-sm text-gray-400">Memory</p>
                  <p className="text-xl font-bold text-white">
                    {data.memory_used_mb} MB
                    <span className="text-sm text-gray-400 font-normal">
                      {data.memory_limit_mb < 999999
                        ? ` / ${formatNumber(data.memory_limit_mb)} MB`
                        : ' (unlimited)'}
                    </span>
                  </p>
                </div>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    getBarColor(getPercentage(data.memory_used_mb, data.memory_limit_mb))
                  )}
                  style={{
                    width: `${getPercentage(data.memory_used_mb, data.memory_limit_mb)}%`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Daily Usage Chart */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-400" />
              Daily Usage (Last 7 Days)
            </h2>

            <div className="flex items-end gap-2 h-48">
              {data.daily_usage.map((day) => (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-2">
                  <div className="w-full flex flex-col items-center">
                    <span className="text-xs text-gray-400 mb-1">
                      {day.messages}
                    </span>
                    <div
                      className="w-full bg-blue-500 rounded-t transition-all"
                      style={{
                        height: `${(day.messages / maxMessages) * 150}px`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-gray-500">
                    {new Date(day.date).toLocaleDateString('en-US', {
                      weekday: 'short',
                    })}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Tier Info */}
          <div className="mt-6 bg-gray-800 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">Current Plan</h2>
                <p className="text-gray-400">
                  {tier === 'free' && 'Free tier with limited usage'}
                  {tier === 'pro' && 'Pro tier with expanded limits'}
                  {tier === 'enterprise' && 'Enterprise tier with unlimited usage'}
                </p>
              </div>
              {tier !== 'enterprise' && (
                <button
                  className={clsx(
                    'px-4 py-2 rounded-lg font-medium',
                    'bg-blue-600 text-white',
                    'hover:bg-blue-700 transition-colors'
                  )}
                >
                  Upgrade Plan
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
