import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  createBillingRecord,
  createSubscription,
  deleteBillingRecord,
  getCompanySubscription,
  listBillingRecords,
  listPlans,
  recalculateStorage,
  updateBillingRecord,
  updateSubscription,
} from '../api/subscriptions'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import Modal from '../components/Modal'
import UsageMeter from '../components/UsageMeter'
import { formatDate, formatDateTime, formatMoney, isoDate } from '../utils/format'

const STATUSES = [
  ['trial', 'Trial'],
  ['active', 'Active'],
  ['past_due', 'Payment overdue'],
  ['suspended', 'Suspended'],
  ['expired', 'Expired'],
  ['cancelled', 'Cancelled'],
]
const PAYMENT_STATUSES = [
  ['pending', 'Pending'],
  ['paid', 'Paid'],
  ['partially_paid', 'Partially paid'],
  ['overdue', 'Overdue'],
  ['refunded', 'Refunded'],
  ['void', 'Void'],
]
const PAYMENT_METHODS = [
  ['', '—'],
  ['bank_transfer', 'Bank transfer'],
  ['upi', 'UPI'],
  ['cash', 'Cash'],
  ['cheque', 'Cheque'],
  ['card', 'Card'],
  ['other', 'Other'],
]

function addMonths(date, months) {
  const next = new Date(date)
  next.setMonth(next.getMonth() + months)
  next.setDate(next.getDate() - 1)
  return next
}

export default function CompanySubscriptionPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [data, setData] = useState(null)
  const [plans, setPlans] = useState([])
  const [billing, setBilling] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editingSubscription, setEditingSubscription] = useState(null)
  const [editingBill, setEditingBill] = useState(null)
  const [saving, setSaving] = useState(false)
  const [recalculating, setRecalculating] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const subscriptionData = await getCompanySubscription(companyId)
      setData(subscriptionData)
      if (isAdmin) {
        const [planData, billingData] = await Promise.all([listPlans(), listBillingRecords(companyId)])
        setPlans(planData)
        setBilling(billingData.results)
      }
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load the subscription.'))
    } finally {
      setLoading(false)
    }
  }, [companyId, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <div className="page-loading">Loading…</div>
  if (!data) return <div className="alert alert-error">{error}</div>

  const { subscription, plan, usage } = data
  const metrics = usage.metrics

  function openAssign(existing) {
    const today = new Date()
    setEditingSubscription(
      existing
        ? { ...existing }
        : {
            plan: plans.find((p) => p.is_active)?.id || '',
            status: 'active',
            start_date: isoDate(today),
            end_date: isoDate(addMonths(today, 1)),
            renewal_date: isoDate(addMonths(today, 1)),
            auto_renew: true,
            price_override: '',
            creative_limit_override: '',
            video_limit_override: '',
            publishing_limit_override: '',
            storage_limit_mb_override: '',
            social_account_limit_override: '',
            notes: '',
          },
    )
  }

  async function saveSubscription(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...editingSubscription, company: Number(companyId) }
      ;['end_date', 'renewal_date'].forEach((key) => {
        if (!payload[key]) payload[key] = null
      })
      ;[
        'price_override', 'creative_limit_override', 'video_limit_override', 'publishing_limit_override',
        'storage_limit_mb_override', 'social_account_limit_override',
      ].forEach((key) => {
        payload[key] = payload[key] === '' || payload[key] === null || payload[key] === undefined ? null : payload[key]
      })
      if (editingSubscription.id) await updateSubscription(editingSubscription.id, payload)
      else await createSubscription(payload)
      setEditingSubscription(null)
      setNotice('Subscription saved.')
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save the subscription.'))
    } finally {
      setSaving(false)
    }
  }

  function openBill(existing) {
    const today = isoDate(new Date())
    setEditingBill(
      existing
        ? { ...existing, invoice_file: null }
        : {
            subscription: subscription?.id || '',
            invoice_number: '',
            invoice_date: today,
            due_date: '',
            period_start: subscription ? usage.period.start : '',
            period_end: subscription ? usage.period.end : '',
            amount: subscription ? subscription.effective_price : '',
            tax_amount: '0',
            amount_paid: '0',
            currency: subscription?.currency || 'INR',
            payment_status: 'pending',
            payment_method: '',
            payment_reference: '',
            paid_on: '',
            notes: '',
            invoice_file: null,
          },
    )
  }

  async function saveBill(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...editingBill }
      ;['due_date', 'period_start', 'period_end', 'paid_on', 'subscription'].forEach((key) => {
        if (payload[key] === '') payload[key] = null
      })
      delete payload.total_amount
      if (editingBill.id) await updateBillingRecord(companyId, editingBill.id, payload)
      else await createBillingRecord(companyId, payload)
      setEditingBill(null)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save the billing record.'))
    } finally {
      setSaving(false)
    }
  }

  async function removeBill(record) {
    if (!window.confirm(`Delete ${record.invoice_number || 'this record'}?`)) return
    try {
      await deleteBillingRecord(companyId, record.id)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete.'))
    }
  }

  async function recalc() {
    setRecalculating(true)
    try {
      await recalculateStorage(companyId)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not recalculate storage.'))
    } finally {
      setRecalculating(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Subscription & usage</h1>
          <p className="page-subtitle">
            {workspace?.company?.name || data.company_name} · usage period {formatDate(usage.period.start)} – {formatDate(usage.period.end)}
          </p>
        </div>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => openAssign(null)} disabled={plans.length === 0}>
            {subscription ? 'Change plan' : 'Assign plan'}
          </button>
        )}
      </div>

      {isAdmin && plans.length === 0 && (
        <div className="alert alert-info">Create a plan under Subscriptions → Plans first, then assign it here.</div>
      )}
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="detail-grid detail-grid-even">
        <div className="card plan-card">
          {subscription ? (
            <>
              <div className="card-header">
                <h2>{subscription.plan_name}</h2>
                <span className={`badge status-badge sub-status-${subscription.status}`}>{subscription.status_display}</span>
              </div>
              <div className="plan-price">
                {formatMoney(subscription.effective_price, subscription.currency)}
                <span className="page-subtitle"> / {plan?.billing_cycle_display?.toLowerCase()}</span>
              </div>
              <dl className="detail-list">
                <div className="detail-row">
                  <dt>Started</dt>
                  <dd>{formatDate(subscription.start_date)}</dd>
                </div>
                <div className="detail-row">
                  <dt>Expires</dt>
                  <dd>
                    {subscription.end_date ? formatDate(subscription.end_date) : 'Open-ended'}
                    {subscription.days_remaining !== null && subscription.days_remaining <= 14 && (
                      <span className="badge status-badge status-pending_approval"> {subscription.days_remaining} days left</span>
                    )}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Renewal</dt>
                  <dd>
                    {subscription.renewal_date ? formatDate(subscription.renewal_date) : '—'}
                    {subscription.auto_renew ? ' · auto-renew reminder' : ''}
                  </dd>
                </div>
                {plan?.features?.length > 0 && (
                  <div className="detail-row">
                    <dt>Includes</dt>
                    <dd>
                      <ul className="plain-list">
                        {plan.features.map((feature) => (
                          <li key={feature}>✓ {feature}</li>
                        ))}
                      </ul>
                    </dd>
                  </div>
                )}
              </dl>
              {isAdmin && (
                <button type="button" className="btn btn-ghost" onClick={() => openAssign(subscription)}>
                  Edit subscription
                </button>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>No active subscription. {isAdmin ? 'Assign a plan to start tracking limits.' : 'Contact your account manager.'}</p>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Usage this period</h2>
            {isAdmin && (
              <button type="button" className="btn-link" onClick={recalc} disabled={recalculating}>
                {recalculating ? 'Recalculating…' : 'Recalculate storage'}
              </button>
            )}
          </div>
          <UsageMeter label="Creative generations" metric={metrics.creative} />
          <UsageMeter label="Video generations" metric={metrics.video} />
          <UsageMeter label="Published posts" metric={metrics.publishing} />
          <UsageMeter label="Storage" metric={metrics.storage} unit="MB" />
          <UsageMeter label="Connected social accounts" metric={metrics.social_accounts} />
          {usage.storage_calculated_at && <p className="page-subtitle">Storage measured {formatDateTime(usage.storage_calculated_at)}</p>}
        </div>
      </div>

      {isAdmin && (
        <>
          <div className="card">
            <div className="card-header">
              <h2>Billing</h2>
              <button type="button" className="btn btn-ghost" onClick={() => openBill(null)}>
                + Add billing record
              </button>
            </div>
            {billing.length === 0 ? (
              <div className="empty-state">
                <p>No invoices or payments recorded yet.</p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="table table-stack">
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Period</th>
                      <th className="num">Total</th>
                      <th className="num">Paid</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {billing.map((record) => (
                      <tr key={record.id}>
                        <td data-label="Invoice">
                          {record.invoice_number || '—'}
                          <div className="page-subtitle">{formatDate(record.invoice_date)}</div>
                          {record.invoice_file && (
                            <a href={record.invoice_file} target="_blank" rel="noreferrer" className="btn-link">
                              Invoice file
                            </a>
                          )}
                        </td>
                        <td data-label="Period">
                          {record.period_start ? `${formatDate(record.period_start)} – ${formatDate(record.period_end)}` : '—'}
                        </td>
                        <td data-label="Total" className="num">{formatMoney(record.total_amount, record.currency)}</td>
                        <td data-label="Paid" className="num">
                          {formatMoney(record.amount_paid, record.currency)}
                          {record.payment_reference && <div className="page-subtitle">{record.payment_method_display} · {record.payment_reference}</div>}
                        </td>
                        <td data-label="Status">
                          <span className={`badge status-badge pay-status-${record.payment_status}`}>{record.payment_status_display}</span>
                        </td>
                        <td className="table-actions">
                          <button type="button" className="btn-link" onClick={() => openBill(record)}>
                            Edit
                          </button>
                          <button type="button" className="btn-link btn-link-danger" onClick={() => removeBill(record)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {data.history?.length > 1 && (
            <div className="card">
              <div className="card-header">
                <h2>Subscription history</h2>
              </div>
              <ul className="plain-list">
                {data.history.map((item) => (
                  <li key={item.id}>
                    <strong>{item.plan_name}</strong> · {item.status_display} · {formatDate(item.start_date)} –{' '}
                    {item.end_date ? formatDate(item.end_date) : 'open'}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {editingSubscription && (
        <Modal title={editingSubscription.id ? 'Edit subscription' : 'Assign plan'} onClose={() => setEditingSubscription(null)} width={640}>
          <form onSubmit={saveSubscription}>
            <div className="field-row">
              <label className="field">
                <span>Plan *</span>
                <select value={editingSubscription.plan} onChange={(e) => setEditingSubscription((s) => ({ ...s, plan: Number(e.target.value) }))} required>
                  <option value="">Choose…</option>
                  {plans.map((p) => (
                    <option key={p.id} value={p.id} disabled={!p.is_active && p.id !== editingSubscription.plan}>
                      {p.name} · {formatMoney(p.price, p.currency)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Status</span>
                <select value={editingSubscription.status} onChange={(e) => setEditingSubscription((s) => ({ ...s, status: e.target.value }))}>
                  {STATUSES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Start date *</span>
                <input type="date" value={editingSubscription.start_date} onChange={(e) => setEditingSubscription((s) => ({ ...s, start_date: e.target.value }))} required />
              </label>
              <label className="field">
                <span>Expiry date</span>
                <input type="date" value={editingSubscription.end_date || ''} onChange={(e) => setEditingSubscription((s) => ({ ...s, end_date: e.target.value }))} />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Renewal date</span>
                <input type="date" value={editingSubscription.renewal_date || ''} onChange={(e) => setEditingSubscription((s) => ({ ...s, renewal_date: e.target.value }))} />
              </label>
              <label className="field">
                <span>Price override</span>
                <input type="number" min="0" step="0.01" value={editingSubscription.price_override ?? ''} placeholder="Plan price" onChange={(e) => setEditingSubscription((s) => ({ ...s, price_override: e.target.value }))} />
              </label>
            </div>
            <details className="override-details">
              <summary>Custom limits for this company (optional)</summary>
              <p className="field-hint-inline">Leave blank to use the plan&apos;s limits. 0 = unlimited.</p>
              <div className="field-row">
                {[
                  ['creative_limit_override', 'Creatives / month'],
                  ['video_limit_override', 'Videos / month'],
                  ['publishing_limit_override', 'Posts / month'],
                  ['storage_limit_mb_override', 'Storage (MB)'],
                  ['social_account_limit_override', 'Social accounts'],
                ].map(([key, label]) => (
                  <label className="field" key={key}>
                    <span>{label}</span>
                    <input type="number" min="0" value={editingSubscription[key] ?? ''} onChange={(e) => setEditingSubscription((s) => ({ ...s, [key]: e.target.value }))} />
                  </label>
                ))}
              </div>
            </details>
            <label className="field-checkbox">
              <input type="checkbox" checked={editingSubscription.auto_renew} onChange={(e) => setEditingSubscription((s) => ({ ...s, auto_renew: e.target.checked }))} />
              Remind me to renew (renewals are recorded manually)
            </label>
            <label className="field">
              <span>Notes</span>
              <textarea rows={2} value={editingSubscription.notes} onChange={(e) => setEditingSubscription((s) => ({ ...s, notes: e.target.value }))} />
            </label>
            {!editingSubscription.id && subscription && (
              <p className="modal-hint">The current subscription ({subscription.plan_name}) will be closed when this one is saved.</p>
            )}
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditingSubscription(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editingBill && (
        <Modal title={editingBill.id ? 'Edit billing record' : 'Add billing record'} onClose={() => setEditingBill(null)} width={640}>
          <form onSubmit={saveBill}>
            <div className="field-row">
              <label className="field">
                <span>Invoice number</span>
                <input value={editingBill.invoice_number} onChange={(e) => setEditingBill((b) => ({ ...b, invoice_number: e.target.value }))} />
              </label>
              <label className="field">
                <span>Invoice date *</span>
                <input type="date" value={editingBill.invoice_date} onChange={(e) => setEditingBill((b) => ({ ...b, invoice_date: e.target.value }))} required />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Period from</span>
                <input type="date" value={editingBill.period_start || ''} onChange={(e) => setEditingBill((b) => ({ ...b, period_start: e.target.value }))} />
              </label>
              <label className="field">
                <span>Period to</span>
                <input type="date" value={editingBill.period_end || ''} onChange={(e) => setEditingBill((b) => ({ ...b, period_end: e.target.value }))} />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Amount *</span>
                <input type="number" step="0.01" min="0" value={editingBill.amount} onChange={(e) => setEditingBill((b) => ({ ...b, amount: e.target.value }))} required />
              </label>
              <label className="field">
                <span>Tax (GST)</span>
                <input type="number" step="0.01" min="0" value={editingBill.tax_amount} onChange={(e) => setEditingBill((b) => ({ ...b, tax_amount: e.target.value }))} />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Payment status</span>
                <select value={editingBill.payment_status} onChange={(e) => setEditingBill((b) => ({ ...b, payment_status: e.target.value }))}>
                  {PAYMENT_STATUSES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Amount paid</span>
                <input type="number" step="0.01" min="0" value={editingBill.amount_paid} onChange={(e) => setEditingBill((b) => ({ ...b, amount_paid: e.target.value }))} />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Payment method</span>
                <select value={editingBill.payment_method} onChange={(e) => setEditingBill((b) => ({ ...b, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Payment reference (UTR / cheque no.)</span>
                <input value={editingBill.payment_reference} onChange={(e) => setEditingBill((b) => ({ ...b, payment_reference: e.target.value }))} />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Due date</span>
                <input type="date" value={editingBill.due_date || ''} onChange={(e) => setEditingBill((b) => ({ ...b, due_date: e.target.value }))} />
              </label>
              <label className="field">
                <span>Paid on</span>
                <input type="date" value={editingBill.paid_on || ''} onChange={(e) => setEditingBill((b) => ({ ...b, paid_on: e.target.value }))} />
              </label>
            </div>
            <label className="field">
              <span>Invoice file (PDF / image)</span>
              <input type="file" accept=".pdf,image/*" onChange={(e) => setEditingBill((b) => ({ ...b, invoice_file: e.target.files?.[0] || null }))} />
            </label>
            <label className="field">
              <span>Notes</span>
              <textarea rows={2} value={editingBill.notes} onChange={(e) => setEditingBill((b) => ({ ...b, notes: e.target.value }))} />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEditingBill(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
