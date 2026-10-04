import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardStats } from '../api/dashboard'
import { extractErrorMessage } from '../api/client'
import ICONS from '../components/DashboardIcons'
import { formatCompact, formatPercent } from '../utils/format'

const numberFormatter = new Intl.NumberFormat('en-US')

function formatNumber(value) {
  return numberFormatter.format(value ?? 0)
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`
}

function StatTile({ icon, tone, value, label, to }) {
  const body = (
    <>
      <div className="stat-tile-icon">{ICONS[icon]}</div>
      <div className="stat-tile-body">
        <div className="stat-tile-value">{value}</div>
        <div className="stat-tile-label">{label}</div>
      </div>
    </>
  )
  return to ? (
    <Link to={to} className={`stat-tile stat-tile-link ${tone ? `stat-tile-${tone}` : ''}`}>
      {body}
    </Link>
  ) : (
    <div className={`stat-tile ${tone ? `stat-tile-${tone}` : ''}`}>{body}</div>
  )
}

const SHORTCUTS = [
  { to: '/companies', icon: 'building', title: 'Companies', text: 'Clients, brands, calendars and every company module.' },
  { to: '/approvals', icon: 'clock', title: 'Approvals', text: 'Everything waiting for client review, across companies.' },
  { to: '/publishing', icon: 'send', title: 'Publishing queue', text: 'Scheduled, published and failed posts.' },
  { to: '/analytics', icon: 'chart', title: 'Analytics', text: 'Reach and engagement for every company.' },
  { to: '/reports', icon: 'file', title: 'Reports', text: 'Company, client, AI usage, approval and subscription reports.' },
  { to: '/subscriptions', icon: 'dollar', title: 'Subscriptions', text: 'Plans, usage limits and manual billing.' },
]

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      setStats(await getDashboardStats())
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load dashboard stats.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <div className="page-loading">Loading…</div>
  if (loadError) return <div className="alert alert-error">{loadError}</div>
  if (!stats) return null

  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
  const publishing = stats.publishing || {}
  const subscriptions = stats.subscriptions || {}
  const engagement = stats.engagement_30d || {}
  const attention = [
    stats.pending_approvals > 0 && { icon: 'clock', tone: 'warning', value: formatNumber(stats.pending_approvals), label: 'Pending approvals', to: '/approvals' },
    publishing.failed > 0 && { icon: 'alert', tone: 'danger', value: formatNumber(publishing.failed), label: 'Failed posts', to: '/publishing' },
    stats.failed_generations > 0 && { icon: 'alert', tone: 'danger', value: formatNumber(stats.failed_generations), label: 'Failed generations', to: '/jobs' },
    publishing.ready_to_publish > 0 && { icon: 'send', tone: 'warning', value: formatNumber(publishing.ready_to_publish), label: 'Approved, not scheduled', to: '/approvals' },
    subscriptions.expiring_soon > 0 && { icon: 'dollar', tone: 'warning', value: formatNumber(subscriptions.expiring_soon), label: 'Plans expiring in 14 days', to: '/subscriptions' },
    subscriptions.companies_without_plan > 0 && { icon: 'building', tone: 'warning', value: formatNumber(subscriptions.companies_without_plan), label: 'Companies without a plan', to: '/subscriptions' },
  ].filter(Boolean)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="dashboard-greeting">{today} · platform overview</p>
        </div>
      </div>

      {attention.length > 0 && (
        <>
          <h2 className="dashboard-section-title">Needs attention</h2>
          <div className="stat-grid">
            {attention.map((tile) => (
              <StatTile key={tile.label} {...tile} />
            ))}
          </div>
        </>
      )}

      <h2 className="dashboard-section-title">Overview</h2>
      <div className="stat-grid">
        <StatTile icon="building" value={formatNumber(stats.total_companies)} label="Total companies" to="/companies" />
        <StatTile icon="check" tone="success" value={formatNumber(stats.active_companies)} label="Active companies" />
        <StatTile icon="users" value={formatNumber(stats.active_clients)} label="Active clients" />
        <StatTile icon="sparkle" value={formatNumber(stats.content_generated)} label="Content generated" />
        <StatTile icon="dollar" value={formatCurrency(stats.ai_usage.total_cost_usd)} label="Tracked AI cost" />
      </div>

      <h2 className="dashboard-section-title">Publishing & performance</h2>
      <div className="stat-grid">
        <StatTile icon="send" tone="success" value={formatNumber(publishing.published_this_month)} label="Published this month" to="/publishing" />
        <StatTile icon="calendar" value={formatNumber(publishing.scheduled)} label="Scheduled posts" to="/publishing" />
        <StatTile icon="chart" value={formatCompact(engagement.reach)} label="Reach (30 days)" to="/analytics" />
        <StatTile icon="sparkle" value={formatPercent(engagement.engagement_rate)} label="Engagement rate (30 days)" to="/analytics" />
        <StatTile icon="dollar" value={formatNumber(subscriptions.active)} label="Active subscriptions" to="/subscriptions" />
      </div>

      <h2 className="dashboard-section-title">Shortcuts</h2>
      <div className="quick-link-grid">
        {SHORTCUTS.map((shortcut) => (
          <Link className="quick-link-card quick-link-card-link" key={shortcut.to} to={shortcut.to}>
            <div className="quick-link-icon">{ICONS[shortcut.icon] || ICONS.sparkle}</div>
            <h2>{shortcut.title}</h2>
            <p>{shortcut.text}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
