import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ApiError, message, read, write } from './api'
import { DataGrid, type Cell } from './data-grid'
import { PipelineInput } from './kaggle-source'

type Mode = 'etl' | 'elt'
type RunStatus = 'in_progress' | 'published' | 'review' | 'failed' | 'unchanged'
type Summary = {
  id: string
  filename: string
  mode: Mode
  month: string
  checksum: string
  status: RunStatus
  step: number
  source_count: number | null
  row_count: number | null
  revenue: string | null
  error: string | null
  error_count: number
  created_at: string
  finalized_at: string | null
}
type Run = Summary & {
  errors: { row: number, message: string }[]
  source_preview: Cell[][]
  clean_preview: Cell[][]
  replacement: Summary | null
  automation: { state: 'queued' | 'running' | 'success' | 'failed' } | null
}
type Comparison = {
  etl: Summary | null
  elt: Summary | null
  matches: boolean | null
  different_orders: number | null
}

const steps = { etl: ['Extract', 'Transform', 'Load'], elt: ['Extract', 'Load', 'Transform'] } as const
const statusLabel: Record<RunStatus, string> = {
  in_progress: 'In progress', published: 'Published', review: 'Needs review', failed: 'Failed', unchanged: 'Unchanged',
}
const money = new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP' })
const orderColumns = ['row_no', 'order_id', 'order_date', 'amount']
const tips = {
  etl: ['Read the CSV with Python.', 'Validate and clean the rows in Python.', 'Load the clean rows into DuckDB.'],
  elt: ['Read the CSV with Python.', 'Load the original values into DuckDB.', 'Validate and clean the rows with SQL.'],
}
const samples = [
  ['november.csv', 'Original orders'],
  ['november-corrected.csv', 'Corrected batch'],
  ['november-invalid.csv', 'Invalid batch'],
]

function thisMonth() {
  const date = new Date()
  return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0')
}

function revenue(value: string | null) {
  return value === null ? '—' : money.format(Number(value))
}

function RunStatusBadge({ status }: { status: RunStatus }) {
  const tone = status === 'published' ? 'active' : status === 'failed' ? 'disabled' : status === 'review' ? 'pending' : ''
  return <span className={'status ' + tone}>{statusLabel[status]}</span>
}

function ComparisonPanel({ month, setMonth, revision }: { month: string, setMonth: (month: string) => void, revision: number }) {
  const [result, setResult] = useState<{ data?: Comparison, error?: string, key: string }>({ key: '' })
  const key = month + ':' + revision

  useEffect(() => {
    if (!month) return
    const controller = new AbortController()
    read<Comparison>('pipelines/compare/?' + new URLSearchParams({ month }), controller.signal)
      .then(data => { if (!controller.signal.aborted) setResult({ key, data }) })
      .catch(err => { if (!controller.signal.aborted) setResult({ key, error: message(err) }) })
    return () => controller.abort()
  }, [month, key])

  const current = result.key === key ? result : undefined
  const data = current?.data
  return (
    <section className="panel compare-panel" aria-labelledby="comparison-title">
      <div className="panel-head"><h2 id="comparison-title">Compare published outputs</h2></div>
      <div className="panel-body">
        <label className="compare-month">Comparison month<input type="month" value={month} onChange={event => setMonth(event.target.value)} /></label>
        {current?.error ? <p className="feedback" role="alert">{current.error}</p>
          : !month ? <p className="muted">Choose a month to compare.</p>
            : !data ? <p className="muted" role="status">Loading comparison…</p>
              : (
                <>
                  <DataGrid name="ETL and ELT comparison" columns={['Mode', 'Valid rows', 'Revenue']}
                    rows={(['etl', 'elt'] as const).map(mode => [mode.toUpperCase(), data[mode]?.row_count ?? 'Not published', revenue(data[mode]?.revenue ?? null)])}
                    empty="" />
                  <p role="status" className={data.matches === true ? 'result-success' : data.matches === false ? 'result-warning' : 'muted'}>
                    {data.matches === null ? 'Publish both modes for this month to compare the clean rows.'
                      : data.matches ? 'Match: order IDs, dates, and amounts are identical.'
                        : `Mismatch: ${data.different_orders} order${data.different_orders === 1 ? '' : 's'} differ.`}
                  </p>
                </>
              )}
      </div>
    </section>
  )
}

function BatchTrail({ run, busy, canAutomate, onNext, onPublish, onAutomate }: {
  run: Run, busy: boolean, canAutomate: boolean, onNext: () => void, onPublish: () => void, onAutomate: () => void,
}) {
  return (
    <section className="panel batch-trail" aria-labelledby="trail-title">
      <div className="panel-head"><h2 id="trail-title">Batch Trail</h2><RunStatusBadge status={run.status} /></div>
      <div className="panel-body">
        <div className="receipt">
          <div><strong>{run.filename}</strong><p className="muted">{run.month} · {run.mode.toUpperCase()}</p></div>
          <dl>
            <div><dt>Source rows</dt><dd>{run.source_count ?? '—'}</dd></div>
            <div><dt>Valid rows</dt><dd>{run.row_count ?? '—'}</dd></div>
            <div><dt>Revenue</dt><dd>{revenue(run.revenue)}</dd></div>
          </dl>
        </div>
        <ol className="trail-steps">
          {steps[run.mode].map((name, index) => {
            const done = index < run.step
            const failed = index === run.step && run.status === 'failed'
            const active = index === run.step && run.status === 'in_progress' && !run.automation
            return <li key={name} className={active ? 'trail-current' : undefined} aria-current={active ? 'step' : undefined}>
              <span className="trail-index">{index + 1}</span>
              <div><strong>{name}</strong><p className="muted">{tips[run.mode][index]}</p></div>
              <span className={failed ? 'result-danger' : done ? 'result-success' : 'muted'}>
                {done ? 'Complete' : failed ? 'Failed' : active ? 'Ready' : 'Waiting'}
              </span>
            </li>
          })}
        </ol>
        {run.automation && <p className="pipeline-notice" role="status">
          Airflow + dbt: {run.automation.state === 'success' ? 'Tests passed' : run.automation.state}.
          {run.status === 'in_progress' && ' Status updates here automatically.'}
        </p>}
        {run.status === 'in_progress' && !run.automation && <div className="pipeline-actions">
          <button className="button primary" type="button" disabled={busy} onClick={onNext}>
            {busy ? 'Working…' : 'Run ' + steps[run.mode][run.step]}
          </button>
          {canAutomate && run.mode === 'elt' && run.step === 0 && (
            <button className="button" type="button" disabled={busy} onClick={onAutomate}>Run with Airflow + dbt</button>
          )}
        </div>}
        {run.error && <div className="feedback pipeline-feedback" role="alert">
          <p>{run.error}</p>
          {run.errors.length > 0 && <ul>{run.errors.map(error => <li key={error.row}>Row {error.row}: {error.message}</li>)}</ul>}
          {run.error_count > run.errors.length && <p>Showing {run.errors.length} of {run.error_count} errors.</p>}
        </div>}
        {run.replacement && <div className="replacement-review">
          <h2>Review replacement</h2>
          <p className="muted">This replaces the whole published month for {run.mode.toUpperCase()}, including removed orders.</p>
          <DataGrid name="Replacement comparison" columns={['Batch', 'Valid rows', 'Revenue']}
            rows={[
              ['Currently published', run.replacement.row_count, revenue(run.replacement.revenue)],
              ['Candidate', run.row_count, revenue(run.revenue)],
            ]} empty="" />
          <button className="button primary" type="button" disabled={busy} onClick={onPublish}>{busy ? 'Publishing…' : 'Replace published batch'}</button>
        </div>}
        {(run.source_preview.length > 0 || run.clean_preview.length > 0) && <div className="run-previews">
          {run.source_preview.length > 0 && <details open={!run.clean_preview.length}>
            <summary>Source rows</summary>
            <DataGrid name="Source rows" columns={orderColumns} rows={run.source_preview} empty="" />
          </details>}
          {run.clean_preview.length > 0 && <details open>
            <summary>Clean rows</summary>
            <DataGrid name="Clean rows" columns={orderColumns} rows={run.clean_preview} empty="" />
          </details>}
        </div>}
        <details className="receipt-details">
          <summary>Run receipt</summary>
          <dl><div><dt>Started</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div>
            <div><dt>Finished</dt><dd>{run.finalized_at ? new Date(run.finalized_at).toLocaleString() : '—'}</dd></div>
            <div><dt>SHA-256</dt><dd>{run.checksum}</dd></div></dl>
        </details>
      </div>
    </section>
  )
}

export function PipelineLab() {
  const [mode, setMode] = useState<Mode>('elt')
  const [month, setMonth] = useState(thisMonth)
  const [comparisonMonth, setComparisonMonth] = useState(month)
  const [run, setRun] = useState<Run | null>(null)
  const [history, setHistory] = useState<Summary[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [canAutomate, setCanAutomate] = useState(false)
  const [automationError, setAutomationError] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    read<{ runs: Summary[], automation_available: boolean }>('pipelines/', controller.signal)
      .then(({ runs, automation_available }) => {
        if (!controller.signal.aborted) {
          setHistory(runs)
          setCanAutomate(automation_available)
        }
      })
      .catch(err => { if (!controller.signal.aborted) setError(message(err)) })
      .finally(() => { if (!controller.signal.aborted) setHistoryLoading(false) })
    return () => controller.abort()
  }, [])

  const show = useCallback((data: Run) => {
    setRun(data)
    setComparisonMonth(data.month)
    setHistory(current => [data, ...current.filter(item => item.id !== data.id)]
      .sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 30))
    if (data.status === 'published') setRevision(current => current + 1)
  }, [])

  const automationId = run?.automation && run.status === 'in_progress' ? run.id : null
  useEffect(() => {
    if (!automationId) return
    const path = 'pipelines/' + automationId + '/sync/'
    let stopped = false
    async function sync() {
      try {
        const { run } = await write<{ run: Run }>(path, 'POST')
        if (stopped) return
        setAutomationError('')
        show(run)
      } catch (err) {
        if (!stopped) setAutomationError(message(err))
      }
      if (!stopped) timer = window.setTimeout(sync, 2500)
    }
    let timer = window.setTimeout(sync, 1000)
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [automationId, show])

  async function perform(action: () => Promise<void>) {
    setError('')
    setNotice('')
    setBusy(true)
    try { await action() } catch (err) { setError(message(err)) } finally { setBusy(false) }
  }

  function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    void perform(async () => {
      const result = await write<{ run: Run, reused: boolean }>('pipelines/', 'POST', data)
      show(result.run)
      if (result.reused) setNotice('This file is already published for the selected month and mode. No rows were added.')
    })
  }

  function openRun(id: string) {
    return read<{ run: Run }>('pipelines/' + id + '/').then(result => show(result.run))
  }

  function runAction(selected: Run, action: 'advance' | 'publish' | 'automate') {
    void perform(async () => {
      try {
        const data = action === 'advance' ? { step: selected.step }
          : action === 'publish' ? { baseline: selected.replacement?.id } : {}
        const result = await write<{ run: Run }>('pipelines/' + selected.id + '/' + action + '/', 'POST', data)
        show(result.run)
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) await openRun(selected.id)
        throw err
      }
    })
  }

  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">Batch Trail</p><h1>Pipeline Lab</h1><p className="muted">Load an orders CSV, run each step, and compare ETL with ELT.</p></div>
        <a className="button" href="/data">Open Data Explorer</a>
      </div>
      {error && <p className="feedback pipeline-feedback" role="alert">{error}</p>}
      {automationId && automationError && <p className="feedback pipeline-feedback" role="alert">{automationError}</p>}
      {notice && <p className="pipeline-notice" role="status">{notice}</p>}
      <PipelineInput<Run> mode={mode} onMode={setMode} busy={busy} onRun={(data, reused) => {
        setError('')
        setNotice(reused ? 'This file is already published for the selected month and mode. No rows were added.' : '')
        show(data)
      }}>
        <form className="panel pipeline-form" onSubmit={upload} aria-label="New pipeline run">
          <label>Orders CSV<input type="file" name="file" accept=".csv,text/csv" required disabled={busy} /></label>
          <label>Batch month<input type="month" name="month" required value={month} onChange={event => setMonth(event.target.value)} /></label>
          <label>Pipeline mode<select name="mode" value={mode} onChange={event => setMode(event.target.value as Mode)}>
            <option value="elt">ELT · SQL transform</option><option value="etl">ETL · Python transform</option>
          </select></label>
          <button className="button primary" disabled={busy}>{busy ? 'Working…' : 'Upload CSV'}</button>
          <details className="pipeline-samples">
            <summary>Try the sample CSVs</summary>
            <p className="muted">Use batch month November 2026. Files can be up to 2 MiB with 10,000 data rows.</p>
            <div>{samples.map(([file, label]) => <a className="text-link" href={'/api/pipelines/samples/' + file + '/'} key={file}>{label}</a>)}</div>
          </details>
        </form>
      </PipelineInput>
      <div className="pipeline-grid">
        <div className="pipeline-main">
          {run ? <BatchTrail run={run} busy={busy} canAutomate={canAutomate}
            onNext={() => runAction(run, 'advance')} onPublish={() => runAction(run, 'publish')} onAutomate={() => runAction(run, 'automate')} />
            : <section className="panel"><div className="panel-head"><h2>Batch Trail</h2></div><p className="panel-empty muted">Upload an orders CSV or open a recent run to get started.</p></section>}
          <ComparisonPanel month={comparisonMonth} setMonth={setComparisonMonth} revision={revision} />
        </div>
        <aside className="panel run-history" aria-labelledby="history-title">
          <div className="panel-head"><h2 id="history-title">Recent runs</h2></div>
          {historyLoading ? <p className="panel-empty muted" role="status">Loading runs…</p>
            : !history.length ? <p className="panel-empty muted">No runs yet.</p>
              : <ul>{history.map(item => (
                <li key={item.id}><button className="history-run" type="button" disabled={busy} aria-pressed={run?.id === item.id}
                  onClick={() => void perform(() => openRun(item.id))}>
                  <strong>{item.filename}</strong><span className="muted">{item.month} · {item.mode.toUpperCase()}</span>
                  <RunStatusBadge status={item.status} />
                </button></li>
              ))}</ul>}
        </aside>
      </div>
    </>
  )
}
