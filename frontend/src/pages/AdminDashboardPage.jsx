import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardStats } from '../api/dashboard'
import { listCompanies } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import ICONS from '../components/DashboardIcons'
import { formatCompact, formatPercent } from '../utils/format'

const numberFormatter = new Intl.NumberFormat('en-US')

function formatNumber(value) {
  return numberFormatter.format(value ?? 0)
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function Metric({ label, value, note, to, icon }) {
  const body = (
    <>
      <span className="adm-metric-head">
        <span className="adm-metric-icon" aria-hidden="true">{ICONS[icon]}</span>
        {label}
      </span>
      <span className="adm-metric-value">{value}</span>
      <span className="adm-metric-note">{note}</span>
    </>
  )
  return to ? (
    <Link to={to} className="adm-metric adm-metric-link">
      {body}
    </Link>
  ) : (
    <div className="adm-metric">{body}</div>
  )
}

export default function AdminDashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [companies, setCompanies] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      setStats(await getDashboardStats())
      listCompanies()
        .then((data) => setCompanies(data.results || []))
        .catch(() => setCompanies([]))
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

  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
  // A person's first name only - an account without a name falls back to its email, which is not a greeting.
  const firstWord = (user?.full_name || '').trim().split(/\s+/)[0]
  const firstName = firstWord.includes('@') ? '' : firstWord
  const publishing = stats.publishing || {}
  const subscriptions = stats.subscriptions || {}
  const engagement = stats.engagement_30d || {}
  const aiUsage = stats.ai_usage || {}

  const attention = [
    stats.pending_approvals > 0 && { icon: 'clock', tone: 'warning', count: stats.pending_approvals, label: 'Waiting for client approval', to: '/approvals' },
    publishing.failed > 0 && { icon: 'alert', tone: 'danger', count: publishing.failed, label: 'Posts failed to publish', to: '/publishing' },
    stats.failed_generations > 0 && { icon: 'alert', tone: 'danger', count: stats.failed_generations, label: 'Generations failed', to: '/jobs' },
    publishing.ready_to_publish > 0 && { icon: 'send', tone: 'warning', count: publishing.ready_to_publish, label: 'Approved but not scheduled', to: '/approvals' },
    subscriptions.expiring_soon > 0 && { icon: 'dollar', tone: 'warning', count: subscriptions.expiring_soon, label: 'Plans expire within 14 days', to: '/subscriptions' },
    subscriptions.companies_without_plan > 0 && { icon: 'building', tone: 'warning', count: subscriptions.companies_without_plan, label: 'Active companies without a plan', to: '/subscriptions' },
  ].filter(Boolean)

  const platform = [
    { label: 'Active companies', value: `${formatNumber(stats.active_companies)} of ${formatNumber(stats.total_companies)}`, to: '/companies' },
    { label: 'Active clients', value: formatNumber(stats.active_clients), to: '/team' },
    { label: 'Scheduled posts', value: formatNumber(publishing.scheduled), to: '/publishing' },
    { label: 'Published, all time', value: formatNumber(publishing.published_total), to: '/publishing' },
    { label: 'Active subscriptions', value: formatNumber(subscriptions.active), to: '/subscriptions' },
  ]

  return (
    <div className="adm">
      <header className="adm-hero">
        <div className="adm-hero-text">
          <span className="adm-eyebrow">{today}</span>
          <h1>
            {greeting()}
            {firstName ? `, ${firstName}` : ''}
          </h1>
          <p>
            {attention.length > 0
              ? `${attention.length} ${attention.length === 1 ? 'thing needs' : 'things need'} you across ${formatNumber(stats.total_companies)} companies.`
              : `Everything is on track across ${formatNumber(stats.total_companies)} companies.`}
          </p>
        </div>
        <div className="adm-hero-actions">
          <Link to="/companies" className="btn btn-ghost">
            <span className="btn-icon" aria-hidden="true">{ICONS.building}</span>
            Companies
          </Link>
          <Link to="/approvals" className="btn btn-accent">
            Review approvals
            {stats.pending_approvals > 0 && <span className="adm-btn-count">{formatNumber(stats.pending_approvals)}</span>}
          </Link>
        </div>
      </header>

      <section className="adm-metrics" aria-label="Key numbers">
        <Metric
          icon="sparkle"
          label="Content generated"
          value={formatNumber(stats.content_generated)}
          note={`${formatNumber(aiUsage.creative_count)} images · ${formatNumber(aiUsage.video_count)} videos`}
          to="/jobs"
        />
        <Metric
          icon="send"
          label="Published this month"
          value={formatNumber(publishing.published_this_month)}
          note={`${formatNumber(publishing.scheduled)} more scheduled`}
          to="/publishing"
        />
        <Metric
          icon="chart"
          label="Reach, last 30 days"
          value={formatCompact(engagement.reach)}
          note={`${formatPercent(engagement.engagement_rate)} engagement rate`}
          to="/analytics"
        />
        <Metric
          icon="dollar"
          label="Tracked AI cost"
          value={formatCurrency(aiUsage.total_cost_usd)}
          note="Across every company"
          to="/subscriptions"
        />
      </section>

      <div className="adm-grid">
        <section className="card adm-companies" aria-labelledby="adm-companies-title">
          <div className="adm-card-head">
            <div>
              <h2 id="adm-companies-title">Companies</h2>
              <p>Open a company to work through its content workflow.</p>
            </div>
            <Link to="/companies" className="adm-link">
              View all {formatNumber(stats.total_companies)}
              <span aria-hidden="true">{ICONS.arrowRight}</span>
            </Link>
          </div>
          {companies.length === 0 ? (
            <div className="empty-state">
              <p>No companies yet.</p>
              <Link to="/companies" className="btn btn-primary">
                Add your first company
              </Link>
            </div>
          ) : (
            <ul className="adm-company-list">
              {companies.slice(0, 6).map((company) => {
                const setup = company.onboarding?.completion_percentage ?? 0
                return (
                  <li key={company.id}>
                    <Link to={`/companies/${company.id}`} className="adm-company">
                      <span className="adm-company-avatar" aria-hidden="true">
                        {company.name.charAt(0).toUpperCase()}
                      </span>
                      <span className="adm-company-main">
                        <span className="adm-company-name">
                          {company.name}
                          {company.status !== 'active' && <span className="adm-company-status">Inactive</span>}
                        </span>
                        <span className="adm-company-meta">
                          {company.industry || 'No industry set'}
                          {typeof company.client_count === 'number' &&
                            ` · ${company.client_count} ${company.client_count === 1 ? 'client' : 'clients'}`}
                        </span>
                      </span>
                      <span className="adm-company-setup" title={`Setup ${setup}% complete`}>
                        <span className="adm-setup-bar">
                          <span style={{ width: `${setup}%` }} />
                        </span>
                        <span className="adm-setup-label">{setup}%</span>
                      </span>
                      <span className="adm-company-open">
                        Open
                        <span aria-hidden="true">{ICONS.arrowRight}</span>
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        <div className="adm-side">
          <section className="card adm-attention" aria-labelledby="adm-attention-title">
            <div className="adm-card-head">
              <h2 id="adm-attention-title">Needs attention</h2>
              {attention.length > 0 && <span className="adm-count">{attention.length}</span>}
            </div>
            {attention.length === 0 ? (
              <div className="adm-clear">
                <span className="adm-clear-icon" aria-hidden="true">{ICONS.check}</span>
                <span>
                  <strong>All clear</strong>
                  Nothing is waiting on you right now.
                </span>
              </div>
            ) : (
              <ul className="adm-attention-list">
                {attention.map((item) => (
                  <li key={item.label}>
                    <Link to={item.to} className={`adm-alert adm-alert-${item.tone}`}>
                      <span className="adm-alert-icon" aria-hidden="true">{ICONS[item.icon]}</span>
                      <span className="adm-alert-label">{item.label}</span>
                      <span className="adm-alert-count">{formatNumber(item.count)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card adm-platform" aria-labelledby="adm-platform-title">
            <div className="adm-card-head">
              <h2 id="adm-platform-title">Platform</h2>
            </div>
            <dl className="adm-kv">
              {platform.map((row) => (
                <div key={row.label}>
                  <dt>{row.label}</dt>
                  <dd>
                    <Link to={row.to}>{row.value}</Link>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </div>
  )
}
