import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { createPlan, deletePlan, getUsageOverview, listPlans, listSubscriptions, updatePlan } from '../api/subscriptions'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import KpiTile from '../components/KpiTile'
import Modal from '../components/Modal'
import Tabs from '../components/Tabs'
import TagsInput from '../components/TagsInput'
import { formatDate, formatMoney, formatNumber } from '../utils/format'

const EMPTY_PLAN = {
  name: '', description: '', price: '', currency: 'INR', billing_cycle: 'monthly',
  creative_limit: 0, video_limit: 0, publishing_limit: 0, storage_limit_mb: 0, social_account_limit: 0,
  allowed_platforms: [], features: [], is_active: true, sort_order: 0,
}
const CYCLES = [
  ['monthly', 'Monthly'],
  ['quarterly', 'Quarterly'],
  ['half_yearly', 'Half-yearly'],
  ['yearly', 'Yearly'],
  ['custom', 'Custom'],
]
const PLATFORMS = [
  ['instagram', 'Instagram'],
  ['facebook', 'Facebook'],
  ['linkedin', 'LinkedIn'],
]

function limitText(value) {
  return value ? formatNumber(value) : '∞'
}

function usageCell(metric) {
  if (!metric) return '—'
  if (metric.unlimited) return `${formatNumber(metric.used)} / ∞`
  return (
    <span className={metric.percentage >= 100 ? 'usage-danger' : metric.percentage >= 80 ? 'usage-warning' : ''}>
      {formatNumber(metric.used)} / {formatNumber(metric.limit)} ({metric.percentage}%)
    </span>
  )
}

export default function SubscriptionsPage() {
  const { isAdmin } = useAuth()
  const [tab, setTab] = useState('overview')
  const [overview, setOverview] = useState(null)
  const [subscriptions, setSubscriptions] = useState([])
  const [plans, setPlans] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingPlan, setEditingPlan] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      if (tab === 'overview') setOverview(await getUsageOverview())
      if (tab === 'subscriptions') setSubscriptions((await listSubscriptions(statusFilter ? { status: statusFilter } : {})).results)
      if (tab === 'plans') setPlans(await listPlans())
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load subscriptions.'))
    } finally {
      setLoading(false)
    }
  }, [tab, statusFilter])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/client" replace />

  async function savePlan(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...editingPlan }
      delete payload.id
      delete payload.active_subscriptions
      if (editingPlan.id) await updatePlan(editingPlan.id, payload)
      else await createPlan(payload)
      setEditingPlan(null)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save the plan.'))
    } finally {
      setSaving(false)
    }
  }

  async function removePlan(plan) {
    if (!window.confirm(`Delete "${plan.name}"? Plans with subscriptions are deactivated instead.`)) return
    try {
      await deletePlan(plan.id)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete the plan.'))
    }
  }

  const summary = overview?.summary
  const outstanding = summary ? (Number(summary.outstanding_amount.total || 0) - Number(summary.outstanding_amount.paid || 0)) : 0

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Subscriptions</h1>
          <p className="page-subtitle">Manually managed plans, subscriptions, usage and billing - no online checkout.</p>
        </div>
        {tab === 'plans' && (
          <button type="button" className="btn btn-primary" onClick={() => setEditingPlan({ ...EMPTY_PLAN })}>
            + New plan
          </button>
        )}
      </div>

      <Tabs
        tabs={[
          { value: 'overview', label: 'Usage overview' },
          { value: 'subscriptions', label: 'Subscriptions' },
          { value: 'plans', label: 'Plans' },
        ]}
        value={tab}
        onChange={(value) => {
          setLoading(true)
          setTab(value)
        }}
      />
      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="page-loading">Loading…</div>
      ) : tab === 'overview' && overview ? (
        <>
          <div className="kpi-grid">
            <KpiTile label="Active subscriptions" value={formatNumber(summary.active + summary.trial)} hint={`${summary.trial} on trial`} />
            <KpiTile label="Expiring in 30 days" value={formatNumber(summary.expiring_30_days)} />
            <KpiTile label="Companies without a plan" value={formatNumber(summary.without_subscription)} />
            <KpiTile label="Outstanding balance" value={formatMoney(outstanding)} hint={`${summary.past_due} payment overdue`} />
          </div>
          <div className="card card-flush">
            <div className="table-wrapper">
              <table className="table table-stack">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Plan</th>
                    <th>Expiry</th>
                    <th>Creatives</th>
                    <th>Videos</th>
                    <th>Posts</th>
                    <th>Storage</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {overview.results.map((row) => (
                    <tr key={row.company_id}>
                      <td data-label="Company">{row.company_name}</td>
                      <td data-label="Plan">
                        {row.subscription ? (
                          <>
                            {row.subscription.plan_name}{' '}
                            <span className={`badge status-badge sub-status-${row.subscription.status}`}>{row.subscription.status_display}</span>
                          </>
                        ) : (
                          <span className="muted">No plan</span>
                        )}
                      </td>
                      <td data-label="Expiry">{row.subscription?.end_date ? formatDate(row.subscription.end_date) : '—'}</td>
                      <td data-label="Creatives">{usageCell(row.usage.metrics.creative)}</td>
                      <td data-label="Videos">{usageCell(row.usage.metrics.video)}</td>
                      <td data-label="Posts">{usageCell(row.usage.metrics.publishing)}</td>
                      <td data-label="Storage">{usageCell(row.usage.metrics.storage)}</td>
                      <td className="table-actions">
                        <Link to={`/companies/${row.company_id}/subscription`} className="btn-link">
                          Manage
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : tab === 'subscriptions' ? (
        <>
          <div className="toolbar">
            <select className="status-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="active,trial,past_due">Current</option>
              <option value="expired">Expired</option>
              <option value="cancelled">Cancelled</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
          {subscriptions.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <p>No subscriptions yet - assign a plan from a company&apos;s Subscription page.</p>
              </div>
            </div>
          ) : (
            <div className="card card-flush">
              <div className="table-wrapper">
                <table className="table table-stack">
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Plan</th>
                      <th>Status</th>
                      <th>Period</th>
                      <th className="num">Price</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {subscriptions.map((s) => (
                      <tr key={s.id}>
                        <td data-label="Company">{s.company_name}</td>
                        <td data-label="Plan">{s.plan_name}</td>
                        <td data-label="Status">
                          <span className={`badge status-badge sub-status-${s.status}`}>{s.status_display}</span>
                        </td>
                        <td data-label="Period">
                          {formatDate(s.start_date)} – {s.end_date ? formatDate(s.end_date) : 'open'}
                          {s.days_remaining !== null && s.days_remaining >= 0 && s.days_remaining <= 14 && (
                            <div className="usage-warning">{s.days_remaining} days left</div>
                          )}
                        </td>
                        <td data-label="Price" className="num">{formatMoney(s.effective_price, s.currency)}</td>
                        <td className="table-actions">
                          <Link to={`/companies/${s.company}/subscription`} className="btn-link">
                            Open
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : tab === 'plans' ? (
        plans.length === 0 ? (
          <div className="card">
            <div className="empty-state">
              <p>No plans yet. Create your first plan (e.g. Starter, Growth, Pro) with its monthly limits.</p>
            </div>
          </div>
        ) : (
          <div className="plan-grid">
            {plans.map((plan) => (
              <div className={`card plan-tile ${plan.is_active ? '' : 'plan-tile-inactive'}`} key={plan.id}>
                <div className="card-header">
                  <h2>{plan.name}</h2>
                  {!plan.is_active && <span className="badge badge-inactive">inactive</span>}
                </div>
                <div className="plan-price">
                  {formatMoney(plan.price, plan.currency)}
                  <span className="page-subtitle"> / {plan.billing_cycle_display.toLowerCase()}</span>
                </div>
                {plan.description && <p className="page-subtitle">{plan.description}</p>}
                <ul className="plain-list plan-limits">
                  <li>{limitText(plan.creative_limit)} creatives / month</li>
                  <li>{limitText(plan.video_limit)} videos / month</li>
                  <li>{limitText(plan.publishing_limit)} posts / month</li>
                  <li>{plan.storage_limit_mb ? `${formatNumber(plan.storage_limit_mb)} MB` : 'Unlimited'} storage</li>
                  <li>{limitText(plan.social_account_limit)} social accounts</li>
                  <li>{plan.allowed_platforms.length ? plan.allowed_platforms.join(', ') : 'All platforms'}</li>
                  {plan.features.map((feature) => (
                    <li key={feature}>✓ {feature}</li>
                  ))}
                </ul>
                <p className="page-subtitle">{plan.active_subscriptions} active subscription(s)</p>
                <div className="modal-actions">
                  <button type="button" className="btn-link btn-link-danger" onClick={() => removePlan(plan)}>
                    Delete
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => setEditingPlan({ ...plan })}>
                    Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : null}

      {editingPlan && (
        <Modal title={editingPlan.id ? `Edit ${editingPlan.name}` : 'New plan'} onClose={() => setEditingPlan(null)} width={680}>
          <form onSubmit={savePlan}>
            <div className="field-row">
              <label className="field">
                <span>Plan name *</span>
                <input value={editingPlan.name} onChange={(e) => setEditingPlan((p) => ({ ...p, name: e.target.value }))} required />
              </label>
              <label className="field">
                <span>Billing cycle</span>
                <select value={editingPlan.billing_cycle} onChange={(e) => setEditingPlan((p) => ({ ...p, billing_cycle: e.target.value }))}>
                  {CYCLES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Price *</span>
                <input type="number" step="0.01" min="0" value={editingPlan.price} onChange={(e) => setEditingPlan((p) => ({ ...p, price: e.target.value }))} required />
              </label>
              <label className="field">
                <span>Currency</span>
                <input value={editingPlan.currency} maxLength={3} onChange={(e) => setEditingPlan((p) => ({ ...p, currency: e.target.value.toUpperCase() }))} />
              </label>
            </div>
            <label className="field">
              <span>Description</span>
              <textarea rows={2} value={editingPlan.description} onChange={(e) => setEditingPlan((p) => ({ ...p, description: e.target.value }))} />
            </label>
            <p className="field-hint-inline">Monthly limits - 0 means unlimited.</p>
            <div className="field-row field-row-3">
              {[
                ['creative_limit', 'Creatives'],
                ['video_limit', 'Videos'],
                ['publishing_limit', 'Published posts'],
                ['storage_limit_mb', 'Storage (MB)'],
                ['social_account_limit', 'Social accounts'],
                ['sort_order', 'Sort order'],
              ].map(([key, label]) => (
                <label className="field" key={key}>
                  <span>{label}</span>
                  <input type="number" min="0" value={editingPlan[key]} onChange={(e) => setEditingPlan((p) => ({ ...p, [key]: Number(e.target.value) }))} />
                </label>
              ))}
            </div>
            <div className="field">
              <span>Allowed platforms (none ticked = all)</span>
              <div className="checkbox-row">
                {PLATFORMS.map(([value, label]) => (
                  <label key={value} className="field-checkbox field-checkbox-inline">
                    <input
                      type="checkbox"
                      checked={editingPlan.allowed_platforms.includes(value)}
                      onChange={(e) =>
                        setEditingPlan((p) => ({
                          ...p,
                          allowed_platforms: e.target.checked ? [...p.allowed_platforms, value] : p.allowed_platforms.filter((v) => v !== value),
                        }))
                      }
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
            <label className="field">
              <span>Features shown on the plan</span>
              <TagsInput value={editingPlan.features} onChange={(v) => setEditingPlan((p) => ({ ...p, features: v }))} placeholder="Type a feature, press Enter" />
            </label>
            <label className="field-checkbox">
              <input type="checkbox" checked={editingPlan.is_active} onChange={(e) => setEditingPlan((p) => ({ ...p, is_active: e.target.checked }))} />
              Active (can be assigned)
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditingPlan(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save plan'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
