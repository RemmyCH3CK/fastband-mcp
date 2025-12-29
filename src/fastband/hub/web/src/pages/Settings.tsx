import { useState } from 'react'
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
} from 'lucide-react'
import { useAuthStore } from '../stores/auth'
import { useSessionStore } from '../stores/session'
import { Layout } from '../components/Layout'

type Tab = 'profile' | 'billing' | 'notifications' | 'security'

const tabs: { id: Tab; label: string; icon: typeof User }[] = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
]

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

  const { user } = useAuthStore()
  const { tier } = useSessionStore()

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
                <button
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg',
                    'bg-red-600/20 text-red-400 border border-red-600/50',
                    'hover:bg-red-600/30 transition-colors'
                  )}
                >
                  <Trash2 className="w-4 h-4" />
                  Delete Account
                </button>
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
    </Layout>
  )
}
