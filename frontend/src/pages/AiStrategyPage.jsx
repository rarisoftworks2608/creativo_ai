import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  generateBrandContext,
  generateStrategyOutput,
  getBrandContext,
  listStrategyOutputs,
} from '../api/aiStrategy'
import { getCompany } from '../api/companies'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'

const PLANNING_KINDS = [
  { kind: 'content_ideas', label: 'Content Ideas', description: 'Concrete post ideas ready to brief a designer or copywriter.' },
  { kind: 'topic_suggestions', label: 'Topic Suggestions', description: 'Broad topics this brand should regularly talk about.' },
  { kind: 'content_themes', label: 'Content Themes', description: 'Recurring themes to organize the content calendar around.' },
  { kind: 'campaign_suggestions', label: 'Campaign Suggestions', description: 'Marketing campaigns worth running.' },
  { kind: 'posting_suggestions', label: 'Posting Suggestions', description: 'Cadence and best times to post, per platform.' },
]

const STRATEGY_KINDS = [
  { kind: 'content_strategy', label: 'Content Strategy', description: 'Overall content pillars and recommendations.' },
  { kind: 'platform_strategy', label: 'Platform Strategy', description: 'How this brand should use each social platform.' },
  { kind: 'audience_strategy', label: 'Audience Strategy', description: 'How to approach each audience segment.' },
  { kind: 'campaign_strategy', label: 'Campaign Strategy', description: 'Specific campaigns with goal, approach and timeline.' },
]

function humanize(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function ResultValue({ value }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <p className="muted">None</p>
    if (typeof value[0] === 'object' && value[0] !== null) {
      return (
        <div className="result-card-grid">
          {value.map((item, i) => (
            <div className="result-card" key={i}>
              {Object.entries(item).map(([k, v]) => (
                <div key={k} className="result-card-row">
                  <span className="result-card-label">{humanize(k)}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )
    }
    return (
      <ul className="result-bullet-list">
        {value.map((v, i) => (
          <li key={i}>{v}</li>
        ))}
      </ul>
    )
  }
  return <p>{value}</p>
}

function StrategyResultView({ result }) {
  if (!result) return null
  return (
    <div className="strategy-result">
      {Object.entries(result).map(([key, value]) => (
        <div key={key} className="strategy-result-section">
          <h4>{humanize(key)}</h4>
          <ResultValue value={value} />
        </div>
      ))}
    </div>
  )
}

export default function AiStrategyPage() {
  const { id: companyId } = useParams()
  const { isAdmin } = useAuth()

  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [brandContext, setBrandContext] = useState(null)
  const [brandContextExpanded, setBrandContextExpanded] = useState(false)
  const [generatingContext, setGeneratingContext] = useState(false)
  const [contextError, setContextError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const companyData = await getCompany(companyId)
      setCompany(companyData)
      try {
        const context = await getBrandContext(companyId)
        setBrandContext(context)
      } catch {
        setBrandContext(null)
      }
    } catch (err) {
      setLoadError(extractErrorMessage(err, 'Could not load this company.'))
    } finally {
      setLoading(false)
    }
  }, [companyId])

  useEffect(() => {
    load()
  }, [load])

  async function handleGenerateContext() {
    setGeneratingContext(true)
    setContextError('')
    try {
      const context = await generateBrandContext(companyId)
      setBrandContext(context)
      setBrandContextExpanded(true)
    } catch (err) {
      setContextError(extractErrorMessage(err, 'Could not generate the brand context.'))
    } finally {
      setGeneratingContext(false)
    }
  }

  if (loading) return <div className="page-loading">Loading…</div>
  if (loadError && !company) return <div className="alert alert-error">{loadError}</div>
  if (!company) return null

  return (
    <div>
      <Link to={`/companies/${companyId}`} className="back-link">
        ← Back to {company.name}
      </Link>

      <div className="page-header">
        <div>
          <h1>AI Content Strategy</h1>
          <p className="page-subtitle">{company.name}</p>
        </div>
      </div>

      {loadError && <div className="alert alert-error">{loadError}</div>}

      <div className="card">
        <div className="card-header">
          <h2>Brand Context</h2>
          {isAdmin && (
            <button type="button" className="btn btn-primary" disabled={generatingContext} onClick={handleGenerateContext}>
              {generatingContext ? 'Generating…' : brandContext ? 'Regenerate' : 'Generate brand context'}
            </button>
          )}
        </div>

        {contextError && <div className="alert alert-error">{contextError}</div>}

        {!brandContext ? (
          <div className="empty-state">
            <p>
              No brand context yet.
              {isAdmin ? ' Generate one to unlock AI Planning and AI Strategy below.' : ' Check back once your account manager has generated one.'}
            </p>
          </div>
        ) : (
          <>
            <p className="modal-hint">
              Generated {new Date(brandContext.updated_at).toLocaleString()} with {brandContext.model_used || 'unknown model'}.
            </p>
            <p>{brandContext.summary}</p>
            <button type="button" className="btn-link" onClick={() => setBrandContextExpanded((v) => !v)}>
              {brandContextExpanded ? 'Hide analysis details' : 'Show analysis details'}
            </button>
            {brandContextExpanded && (
              <dl className="detail-list" style={{ marginTop: 12 }}>
                <div className="detail-row">
                  <dt>Business</dt>
                  <dd>{brandContext.business_analysis || <span className="muted">Not set</span>}</dd>
                </div>
                <div className="detail-row">
                  <dt>Brand guidelines</dt>
                  <dd>{brandContext.brand_guidelines_analysis || <span className="muted">Not set</span>}</dd>
                </div>
                <div className="detail-row">
                  <dt>Products / services</dt>
                  <dd>{brandContext.products_services_analysis || <span className="muted">Not set</span>}</dd>
                </div>
                <div className="detail-row">
                  <dt>Audience</dt>
                  <dd>{brandContext.audience_analysis || <span className="muted">Not set</span>}</dd>
                </div>
              </dl>
            )}
          </>
        )}
      </div>

      <h2 style={{ marginTop: 32 }}>AI Planning</h2>
      <div className="kind-grid">
        {PLANNING_KINDS.map((spec) => (
          <StrategyKindCard key={spec.kind} companyId={companyId} spec={spec} enabled={Boolean(brandContext)} canGenerate={isAdmin} />
        ))}
      </div>

      <h2 style={{ marginTop: 32 }}>AI Strategy</h2>
      <div className="kind-grid">
        {STRATEGY_KINDS.map((spec) => (
          <StrategyKindCard key={spec.kind} companyId={companyId} spec={spec} enabled={Boolean(brandContext)} canGenerate={isAdmin} />
        ))}
      </div>
    </div>
  )
}

function StrategyKindCard({ companyId, spec, enabled, canGenerate }) {
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [historyExpanded, setHistoryExpanded] = useState(false)
  const [loadingLatest, setLoadingLatest] = useState(true)
  const [notes, setNotes] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoadingLatest(true)
    listStrategyOutputs(companyId, { kind: spec.kind })
      .then((data) => {
        if (cancelled) return
        setHistory(data.results)
        setLatest(data.results[0] || null)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingLatest(false)
      })
    return () => {
      cancelled = true
    }
  }, [companyId, spec.kind])

  async function handleGenerate() {
    setGenerating(true)
    setError('')
    try {
      const output = await generateStrategyOutput(companyId, spec.kind, notes)
      setLatest(output)
      setHistory((prev) => [output, ...prev])
      setNotes('')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not generate this.'))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="card kind-card">
      <div className="card-header">
        <h3>{spec.label}</h3>
      </div>
      <p className="page-subtitle">{spec.description}</p>

      {!enabled ? (
        <p className="muted">{canGenerate ? 'Generate the brand context above first.' : 'Not available yet.'}</p>
      ) : (
        <>
          {canGenerate && (
            <div className="kind-card-actions">
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional guidance for this generation"
              />
              <button type="button" className="btn btn-ghost" disabled={generating} onClick={handleGenerate}>
                {generating ? 'Generating…' : latest ? 'Regenerate' : 'Generate'}
              </button>
            </div>
          )}

          {error && <div className="alert alert-error">{error}</div>}

          {loadingLatest ? (
            <p className="muted">Loading…</p>
          ) : latest ? (
            <>
              <p className="modal-hint">
                {new Date(latest.created_at).toLocaleString()}
                {latest.notes ? ` — "${latest.notes}"` : ''}
              </p>
              <StrategyResultView result={latest.result} />
              {history.length > 1 && (
                <button type="button" className="btn-link" onClick={() => setHistoryExpanded((v) => !v)}>
                  {historyExpanded ? 'Hide history' : `View history (${history.length})`}
                </button>
              )}
              {historyExpanded && (
                <ul className="checklist" style={{ marginTop: 8 }}>
                  {history.slice(1).map((entry) => (
                    <li key={entry.id}>
                      {new Date(entry.created_at).toLocaleString()}
                      {entry.notes ? ` — "${entry.notes}"` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="muted">Not generated yet.</p>
          )}
        </>
      )}
    </div>
  )
}
