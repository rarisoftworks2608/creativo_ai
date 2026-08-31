import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardStats } from '../api/dashboard'
import { extractErrorMessage } from '../api/client'
import ICONS from '../components/DashboardIcons'

const numberFormatter = new Intl.NumberFormat('en-US')

function formatNumber(value) {
  return numberFormatter.format(value ?? 0)
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`
}

function StatTile({ icon, tone, value, label }) {
  return (
    <div className={`stat-tile ${tone ? `stat-tile-${tone}` : ''}`}>
      <div className="stat-tile-icon">{ICONS[icon]}</div>
      <div className="stat-tile-body">
        <div className="stat-tile-value">{value}</div>
        <div className="stat-tile-label">{label}</div>
      </div>
    </div>
  )
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await getDashboardStats()
      setStats(data)
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
  const hasAttention = stats.pending_approvals > 0 || stats.failed_generations > 0

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="dashboard-greeting">{today} · platform overview</p>
        </div>
      </div>

      {hasAttention && (
        <>
          <h2 className="dashboard-section-title">Needs attention</h2>
          <div className="stat-grid">
            {stats.pending_approvals > 0 && (
              <StatTile
                icon="clock"
                tone="warning"
                value={formatNumber(stats.pending_approvals)}
                label="Pending approvals"
              />
            )}
            {stats.failed_generations > 0 && (
              <StatTile
                icon="alert"
                tone="danger"
                value={formatNumber(stats.failed_generations)}
                label="Failed generations"
              />
            )}
          </div>
        </>
      )}

      <h2 className="dashboard-section-title">Overview</h2>
      <div className="stat-grid">
        <StatTile icon="building" value={formatNumber(stats.total_companies)} label="Total companies" />
        <StatTile icon="check" tone="success" value={formatNumber(stats.active_companies)} label="Active companies" />
        <StatTile icon="users" value={formatNumber(stats.active_clients)} label="Active clients" />
        <StatTile icon="sparkle" value={formatNumber(stats.content_generated)} label="Content generated" />
        <StatTile icon="dollar" value={formatCurrency(stats.ai_usage.total_cost_usd)} label="AI usage cost" />
      </div>

      <h2 className="dashboard-section-title">Quick links</h2>
      <div className="detail-grid">
        <div className="card">
          <div className="card-header">
            <h2>Companies</h2>
          </div>
          <p className="page-subtitle">Manage every company on the platform.</p>
          <Link to="/companies" className="btn btn-primary">
            View companies
          </Link>
        </div>
        <div className="card">
          <div className="card-header">
            <h2>Team</h2>
          </div>
          <p className="page-subtitle">Manage admin logins.</p>
          <Link to="/team" className="btn btn-primary">
            View team
          </Link>
        </div>
      </div>
    </div>
  )
}
