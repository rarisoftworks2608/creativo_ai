import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { getAnalyticsOverview } from '../api/analytics'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import BarList from '../components/charts/BarList'
import ChartTable from '../components/charts/ChartTable'
import KpiTile from '../components/KpiTile'
import { formatCompact, formatNumber, formatPercent } from '../utils/format'

export default function AnalyticsOverviewPage() {
  const { isAdmin } = useAuth()
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await getAnalyticsOverview(days))
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load analytics.'))
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  if (!isAdmin) return <Navigate to="/client" replace />
  if (loading) return <div className="page-loading">Loading…</div>

  const ranked = (data?.companies || []).filter((c) => c.posts > 0 || c.engagements > 0)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Analytics overview</h1>
          <p className="page-subtitle">Performance across every company. Open a company for its full dashboard.</p>
        </div>
      </div>

      <div className="filter-row">
        <select className="status-select" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Date range">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={365}>Last 12 months</option>
        </select>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {data && (
        <>
          <div className="kpi-grid">
            <KpiTile label="Posts published" value={formatNumber(data.totals.posts)} />
            <KpiTile label="Reach" value={formatCompact(data.totals.reach)} />
            <KpiTile label="Engagements" value={formatCompact(data.totals.engagements)} />
            <KpiTile label="Engagement rate" value={formatPercent(data.totals.engagement_rate)} />
          </div>

          <div className="card chart-card">
            <div className="card-header">
              <div>
                <h2>Engagements by company</h2>
                <p className="page-subtitle">Last {data.days} days</p>
              </div>
            </div>
            {ranked.length === 0 ? (
              <div className="empty-state">
                <p>No published content with metrics in this period.</p>
              </div>
            ) : (
              <BarList
                ariaLabel="Engagements by company"
                rows={ranked.slice(0, 12).map((c) => ({ key: c.company_id, label: c.company_name, value: c.engagements, row: c }))}
                formatValue={formatCompact}
                detail={({ row }) => `${formatNumber(row.posts)} posts · ${formatNumber(row.reach)} reach · ${formatPercent(row.engagement_rate)} rate`}
              />
            )}
            <ChartTable
              caption="Performance by company"
              columns={[
                { key: 'company_name', label: 'Company' },
                { key: 'posts', label: 'Posts', numeric: true, format: formatNumber },
                { key: 'reach', label: 'Reach', numeric: true, format: formatNumber },
                { key: 'engagements', label: 'Engagements', numeric: true, format: formatNumber },
                { key: 'engagement_rate', label: 'Rate', numeric: true, format: (v) => formatPercent(v) },
              ]}
              rows={data.companies}
            />
          </div>

          <div className="card card-flush">
            <div className="table-wrapper">
              <table className="table table-stack">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th className="num">Posts</th>
                    <th className="num">Reach</th>
                    <th className="num">Engagements</th>
                    <th className="num">Rate</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.companies.map((c) => (
                    <tr key={c.company_id}>
                      <td data-label="Company">{c.company_name}</td>
                      <td data-label="Posts" className="num">{formatNumber(c.posts)}</td>
                      <td data-label="Reach" className="num">{formatNumber(c.reach)}</td>
                      <td data-label="Engagements" className="num">{formatNumber(c.engagements)}</td>
                      <td data-label="Rate" className="num">{formatPercent(c.engagement_rate)}</td>
                      <td className="table-actions">
                        <Link to={`/companies/${c.company_id}/analytics`} className="btn-link">
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
