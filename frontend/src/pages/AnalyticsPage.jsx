import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getAnalyticsSummary, listAnalyticsSyncLogs, listPostMetrics, syncAnalytics } from '../api/analytics'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCompanyWorkspace } from '../context/CompanyWorkspaceContext'
import BarList from '../components/charts/BarList'
import ChartTable from '../components/charts/ChartTable'
import LineChart from '../components/charts/LineChart'
import KpiTile from '../components/KpiTile'
import Sparkline from '../components/charts/Sparkline'
import {
  formatCompact,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatShortDay,
  platformLabel,
  rangePreset,
  timeAgo,
} from '../utils/format'

const PRESETS = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: 'month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
  { value: 'custom', label: 'Custom' },
]
const TREND_METRICS = [
  { value: 'engagements', label: 'Engagements' },
  { value: 'reach', label: 'Reach' },
  { value: 'impressions', label: 'Impressions' },
  { value: 'posts', label: 'Posts' },
]

export default function AnalyticsPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()
  const workspace = useCompanyWorkspace()

  const [preset, setPreset] = useState('30d')
  const [range, setRange] = useState(rangePreset('30d'))
  const [platform, setPlatform] = useState('')
  const [trendMetric, setTrendMetric] = useState('engagements')
  const [data, setData] = useState(null)
  const [posts, setPosts] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refetching, setRefetching] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [syncing, setSyncing] = useState(false)
  const firstLoad = useRef(true)

  const load = useCallback(async () => {
    if (firstLoad.current) setLoading(true)
    else setRefetching(true)
    setError('')
    try {
      const params = { start: range.start, end: range.end, platform }
      const [summary, postData] = await Promise.all([
        getAnalyticsSummary(companyId, params),
        listPostMetrics(companyId, { ...params, ordering: '-engagements' }),
      ])
      setData(summary)
      setPosts(postData.results)
      if (isAdmin) setLogs((await listAnalyticsSyncLogs(companyId)).results.slice(0, 5))
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load analytics.'))
    } finally {
      firstLoad.current = false
      setLoading(false)
      setRefetching(false)
    }
  }, [companyId, range, platform, isAdmin])

  useEffect(() => {
    load()
  }, [load])

  function choosePreset(value) {
    setPreset(value)
    if (value !== 'custom') setRange(rangePreset(value))
  }

  async function handleSync() {
    setSyncing(true)
    setNotice('')
    setError('')
    try {
      const result = await syncAnalytics(companyId)
      setNotice(result.detail)
      setTimeout(load, 8000)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not start a sync.'))
    } finally {
      setSyncing(false)
    }
  }

  const trend = useMemo(
    () => (data?.timeline || []).map((day) => ({ label: day.date, value: day[trendMetric] || 0 })),
    [data, trendMetric],
  )

  if (loading) return <div className="page-loading">Loading…</div>

  const totals = data?.totals
  const hasData = totals && (totals.posts > 0 || data.followers.accounts.length > 0)
  const trendLabel = TREND_METRICS.find((m) => m.value === trendMetric)?.label

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <p className="page-subtitle">
            {workspace?.company?.name ? `${workspace.company.name} · ` : ''}
            {data?.last_synced_at ? `Metrics updated ${timeAgo(data.last_synced_at)}` : 'Metrics sync automatically after publishing'}
          </p>
        </div>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={handleSync} disabled={syncing}>
            {syncing ? 'Starting…' : 'Sync now'}
          </button>
        )}
      </div>

      <div className="filter-row" role="group" aria-label="Analytics filters">
        <select className="status-select" value={preset} onChange={(e) => choosePreset(e.target.value)} aria-label="Date range">
          {PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        {preset === 'custom' && (
          <>
            <input type="date" value={range.start} max={range.end} onChange={(e) => setRange((r) => ({ ...r, start: e.target.value }))} aria-label="Start date" />
            <input type="date" value={range.end} min={range.start} onChange={(e) => setRange((r) => ({ ...r, end: e.target.value }))} aria-label="End date" />
          </>
        )}
        <select className="status-select" value={platform} onChange={(e) => setPlatform(e.target.value)} aria-label="Platform">
          <option value="">All platforms</option>
          <option value="instagram">Instagram</option>
          <option value="facebook">Facebook</option>
          <option value="linkedin">LinkedIn</option>
        </select>
        <span className="filter-range">
          {formatDate(range.start)} – {formatDate(range.end)}
        </span>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}
      {data?.metrics_pending > 0 && (
        <div className="alert alert-info">
          {data.metrics_pending} published post{data.metrics_pending === 1 ? '' : 's'} not synced yet - numbers will appear after the next
          sync{isAdmin ? ' (or click Sync now)' : ''}.
        </div>
      )}

      {!hasData ? (
        <div className="card">
          <div className="empty-state">
            <p>No analytics for this period yet. Performance numbers appear once content is published and synced from the platforms.</p>
          </div>
        </div>
      ) : (
        <div className={refetching ? 'is-refetching' : ''}>
          <div className="kpi-grid">
            <KpiTile label="Posts published" value={formatNumber(totals.posts)} change={data.changes.posts} />
            <KpiTile label="Reach" value={formatCompact(totals.reach)} change={data.changes.reach} />
            <KpiTile label="Impressions" value={formatCompact(totals.impressions)} change={data.changes.impressions} />
            <KpiTile label="Engagements" value={formatCompact(totals.engagements)} change={data.changes.engagements} />
            <KpiTile label="Engagement rate" value={formatPercent(totals.engagement_rate)} change={data.changes.engagement_rate} />
            <KpiTile
              label="Followers"
              value={formatCompact(data.followers.total)}
              hint={
                data.followers.growth !== 0
                  ? `${data.followers.growth > 0 ? '+' : ''}${formatNumber(data.followers.growth)} in this period`
                  : 'No change in this period'
              }
            />
          </div>

          <div className="card chart-card">
            <div className="card-header card-header-wrap">
              <div>
                <h2>{trendLabel} per day</h2>
                <p className="page-subtitle">By publish date of each post</p>
              </div>
              <div className="segmented" role="group" aria-label="Trend measure">
                {TREND_METRICS.map((metric) => (
                  <button key={metric.value} type="button" className={trendMetric === metric.value ? 'active' : ''} onClick={() => setTrendMetric(metric.value)}>
                    {metric.label}
                  </button>
                ))}
              </div>
            </div>
            <LineChart
              data={trend}
              formatLabel={formatShortDay}
              formatValue={formatNumber}
              seriesName={trendLabel}
              ariaLabel={`${trendLabel} per day, ${formatDate(range.start)} to ${formatDate(range.end)}`}
            />
            <ChartTable
              caption={`${trendLabel} per day`}
              columns={[
                { key: 'date', label: 'Date', format: (v) => formatDate(v) },
                { key: 'posts', label: 'Posts', numeric: true, format: formatNumber },
                { key: 'reach', label: 'Reach', numeric: true, format: formatNumber },
                { key: 'impressions', label: 'Impressions', numeric: true, format: formatNumber },
                { key: 'engagements', label: 'Engagements', numeric: true, format: formatNumber },
              ]}
              rows={(data.timeline || []).filter((d) => d.posts || d.reach || d.engagements)}
            />
          </div>

          <div className="detail-grid detail-grid-even">
            <div className="card chart-card">
              <div className="card-header">
                <div>
                  <h2>Engagement rate by platform</h2>
                  <p className="page-subtitle">
                    {data.best_platform ? `Best: ${platformLabel(data.best_platform)}` : 'Engagements ÷ reach'}
                  </p>
                </div>
              </div>
              <BarList
                ariaLabel="Engagement rate by platform"
                rows={data.by_platform.map((row) => ({ key: row.platform, label: platformLabel(row.platform), value: row.engagement_rate, row }))}
                formatValue={(v) => formatPercent(v)}
                detail={({ row }) => `${formatNumber(row.posts)} posts · ${formatNumber(row.reach)} reach · ${formatNumber(row.engagements)} engagements`}
              />
              <ChartTable
                caption="Performance by platform"
                columns={[
                  { key: 'platform', label: 'Platform', format: platformLabel },
                  { key: 'posts', label: 'Posts', numeric: true, format: formatNumber },
                  { key: 'reach', label: 'Reach', numeric: true, format: formatNumber },
                  { key: 'likes', label: 'Likes', numeric: true, format: formatNumber },
                  { key: 'comments', label: 'Comments', numeric: true, format: formatNumber },
                  { key: 'shares', label: 'Shares', numeric: true, format: formatNumber },
                  { key: 'saves', label: 'Saves', numeric: true, format: formatNumber },
                  { key: 'engagement_rate', label: 'Rate', numeric: true, format: (v) => formatPercent(v) },
                ]}
                rows={data.by_platform}
              />
            </div>

            <div className="card chart-card">
              <div className="card-header">
                <div>
                  <h2>Engagement rate by content type</h2>
                  <p className="page-subtitle">{data.best_content_type ? `Best: ${data.best_content_type}` : 'What resonates most'}</p>
                </div>
              </div>
              <BarList
                ariaLabel="Engagement rate by content type"
                rows={data.by_content_type.slice(0, 8).map((row) => ({ key: row.content_type, label: row.content_type, value: row.engagement_rate, row }))}
                formatValue={(v) => formatPercent(v)}
                detail={({ row }) => `${formatNumber(row.posts)} posts · ${formatNumber(row.engagements)} engagements`}
              />
              <ChartTable
                caption="Performance by content type"
                columns={[
                  { key: 'content_type', label: 'Content type' },
                  { key: 'posts', label: 'Posts', numeric: true, format: formatNumber },
                  { key: 'reach', label: 'Reach', numeric: true, format: formatNumber },
                  { key: 'engagements', label: 'Engagements', numeric: true, format: formatNumber },
                  { key: 'engagement_rate', label: 'Rate', numeric: true, format: (v) => formatPercent(v) },
                ]}
                rows={data.by_content_type}
              />
            </div>
          </div>

          {data.followers.accounts.length > 0 && (
            <>
              <h2 className="dashboard-section-title">Followers</h2>
              <div className="kpi-grid">
                {data.followers.accounts.map((account) => (
                  <div className="kpi-tile" key={account.account_id}>
                    <div className="kpi-label">
                      {platformLabel(account.platform)} · {account.account_name}
                    </div>
                    <div className="kpi-value">{account.followers !== null ? formatCompact(account.followers) : '—'}</div>
                    <div className={`kpi-delta ${account.growth > 0 ? 'kpi-delta-good' : account.growth < 0 ? 'kpi-delta-bad' : 'kpi-delta-flat'}`}>
                      <span aria-hidden="true">{account.growth > 0 ? '▲' : account.growth < 0 ? '▼' : '■'}</span>
                      {account.growth === null ? 'No history yet' : `${account.growth > 0 ? '+' : ''}${formatNumber(account.growth)} in period`}
                    </div>
                    <Sparkline values={account.series.map((s) => s.followers)} ariaLabel={`${account.account_name} followers trend`} />
                  </div>
                ))}
              </div>
            </>
          )}

          {data.top_posts.length > 0 && (
            <>
              <h2 className="dashboard-section-title">Top posts</h2>
              <div className="top-posts">
                {data.top_posts.map((post, index) => (
                  <div className="card top-post" key={post.job_id}>
                    <div className="top-post-rank">#{index + 1}</div>
                    {post.media?.[0]?.kind === 'image' ? (
                      <img src={post.media[0].url} alt="" className="top-post-thumb" />
                    ) : (
                      <div className="top-post-thumb top-post-thumb-video" aria-hidden="true">
                        {post.media?.[0]?.kind === 'video' ? '▶' : '—'}
                      </div>
                    )}
                    <div className="top-post-body">
                      <strong>{post.topic || 'Post'}</strong>
                      <span className="page-subtitle">
                        {platformLabel(post.platform)} · {formatDate(post.published_at)}
                      </span>
                      <span className="top-post-stats">
                        {formatCompact(post.reach)} reach · {formatCompact(post.engagements)} engagements · {formatPercent(post.engagement_rate)}
                      </span>
                      {post.url && (
                        <a href={post.url} target="_blank" rel="noreferrer" className="btn-link">
                          View post ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {data.campaigns.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2>Campaign performance</h2>
              </div>
              <div className="table-wrapper">
                <table className="table table-stack">
                  <thead>
                    <tr>
                      <th>Campaign</th>
                      <th className="num">Posts</th>
                      <th className="num">Reach</th>
                      <th className="num">Engagements</th>
                      <th className="num">Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.campaigns.map((campaign) => (
                      <tr key={campaign.campaign}>
                        <td data-label="Campaign">{campaign.campaign}</td>
                        <td data-label="Posts" className="num">{formatNumber(campaign.posts)}</td>
                        <td data-label="Reach" className="num">{formatNumber(campaign.reach)}</td>
                        <td data-label="Engagements" className="num">{formatNumber(campaign.engagements)}</td>
                        <td data-label="Rate" className="num">{formatPercent(campaign.engagement_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {posts.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2>All published posts</h2>
              </div>
              <div className="table-wrapper">
                <table className="table table-stack">
                  <thead>
                    <tr>
                      <th>Post</th>
                      <th>Platform</th>
                      <th className="num">Reach</th>
                      <th className="num">Likes</th>
                      <th className="num">Comments</th>
                      <th className="num">Shares</th>
                      <th className="num">Saves</th>
                      <th className="num">Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {posts.map((post) => (
                      <tr key={post.id}>
                        <td data-label="Post">
                          {post.url ? (
                            <a href={post.url} target="_blank" rel="noreferrer">
                              {post.topic || 'Post'}
                            </a>
                          ) : (
                            post.topic || 'Post'
                          )}
                          <div className="page-subtitle">{formatDateTime(post.published_at)}</div>
                          {post.sync_error && <div className="cell-error">{post.sync_error}</div>}
                        </td>
                        <td data-label="Platform">{platformLabel(post.platform)}</td>
                        <td data-label="Reach" className="num">{formatNumber(post.reach)}</td>
                        <td data-label="Likes" className="num">{formatNumber(post.likes)}</td>
                        <td data-label="Comments" className="num">{formatNumber(post.comments)}</td>
                        <td data-label="Shares" className="num">{formatNumber(post.shares)}</td>
                        <td data-label="Saves" className="num">{formatNumber(post.saves)}</td>
                        <td data-label="Rate" className="num">{formatPercent(post.engagement_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {isAdmin && logs.length > 0 && (
        <details className="card sync-logs">
          <summary>Sync history</summary>
          <ul className="plain-list">
            {logs.map((log) => (
              <li key={log.id}>
                <span className={`badge status-badge sync-${log.status}`}>{log.status_display}</span> {formatDateTime(log.started_at)} ·{' '}
                {log.posts_synced} posts, {log.accounts_synced} accounts
                {log.posts_failed ? `, ${log.posts_failed} failed` : ''}
                {log.errors?.length > 0 && <div className="cell-error">{log.errors[0].message}</div>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
