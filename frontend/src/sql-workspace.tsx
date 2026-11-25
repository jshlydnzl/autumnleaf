import { useEffect, useRef, useState, type FormEvent } from 'react'
import { message, read, write } from './api'
import { DataGrid } from './data-grid'
import { currentSelection, BatchFilters, useSelectionData, type Selection, type Snapshot } from './workbench-data'
import { runWorksheet, SQL_LIMIT, type WorksheetResult } from './worksheet-engine'
import './workbench.css'

type Saved = { name: string, sql: string }
const tables = [
  { name: 'mart.daily_sales', columns: 'mode, month, order_date, order_count, revenue' },
  { name: 'mart.orders', columns: 'order_id, order_date, amount' },
]
const defaultSql = 'SELECT order_date, order_count, revenue\nFROM mart.daily_sales\nORDER BY order_date;'

export default function SqlWorkspace() {
  const [selection, setSelection] = useState(currentSelection)
  const [revision, setRevision] = useState(0)
  const [sql, setSql] = useState(defaultSql)
  const [result, setResult] = useState<WorksheetResult | null>(null)
  const [queryError, setQueryError] = useState('')
  const [running, setRunning] = useState(false)
  const [name, setName] = useState('')
  const [saved, setSaved] = useState<Saved[]>([])
  const [saveError, setSaveError] = useState('')
  const [savedNotice, setSavedNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const job = useRef<AbortController | null>(null)
  const { current, loading } = useSelectionData<Snapshot>('analysis/snapshot/', selection, revision)
  const snapshot = current?.data

  useEffect(() => {
    const request = new AbortController()
    read<{ queries: Saved[] }>('analysis/queries/', request.signal)
      .then(({ queries }) => { if (!request.signal.aborted) setSaved(queries) })
      .catch(err => { if (!request.signal.aborted) setSaveError(message(err)) })
    return () => { request.abort(); job.current?.abort() }
  }, [])

  function choose(next: Selection) {
    job.current?.abort()
    setRunning(false)
    setResult(null)
    setQueryError('')
    setSelection(next)
  }

  async function run() {
    if (!snapshot?.batch || !sql.trim() || running) return
    const controller = new AbortController()
    job.current = controller
    setRunning(true)
    setResult(null)
    setQueryError('')
    try {
      const next = await runWorksheet(sql, snapshot, controller.signal)
      if (!controller.signal.aborted) setResult(next)
    } catch (err) {
      if (!controller.signal.aborted) setQueryError(err instanceof Error ? err.message : 'Could not run the query.')
    } finally {
      if (job.current === controller) setRunning(false)
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving || !name.trim() || !sql.trim()) return
    setSaving(true)
    setSavedNotice('')
    setSaveError('')
    try {
      const { queries } = await write<{ queries: Saved[] }>('analysis/queries/', 'POST', { name, sql })
      setSaved(queries)
      setSavedNotice('Query saved.')
    } catch (err) {
      setSaveError(message(err))
    } finally {
      setSaving(false)
    }
  }

  return <>
    <div className="page-heading">
      <div><p className="eyebrow">Your warehouse</p><h1>SQL Workspace</h1><p className="muted">Run read-only SQL on a copy of a published batch. Your warehouse stays unchanged.</p></div>
      <a className="button" href="/reports">Open Reports</a>
    </div>
    <section className="panel workbench-tools" aria-label="SQL snapshot">
      <BatchFilters selection={selection} onChange={choose} />
      <button type="button" className="button" disabled={running || loading || !selection.month}
        onClick={() => { setResult(null); setQueryError(''); setRevision(n => n + 1) }}>Refresh snapshot</button>
      {loading && <p role="status" className="muted">Loading the published batch…</p>}
      {current?.error && <p role="alert" className="feedback">{current.error}</p>}
      {snapshot && <p className="muted">{snapshot.batch ? snapshot.order_count + ' published orders' : 'No published batch for this month and mode.'}</p>}
    </section>
    <div className="worksheet-layout">
      <aside className="panel worksheet-tables" aria-label="Snapshot tables">
        <div className="panel-head"><h2>Tables</h2></div>
        <div className="panel-body">
          {tables.map(table => <div key={table.name}>
            <button className="button" type="button" disabled={running}
              onClick={() => setSql('SELECT *\nFROM ' + table.name + ';')}>{table.name}</button>
            <p className="muted">{table.columns}</p>
          </div>)}
          <h2>Saved queries</h2>
          {saved.length === 0 && <p className="muted">No saved queries yet.</p>}
          {saved.map(item => <button className="button" type="button" key={item.name} disabled={running}
            onClick={() => { setName(item.name); setSql(item.sql); setSavedNotice('') }}>{item.name}</button>)}
        </div>
      </aside>
      <section aria-label="Worksheet" className="panel">
        <div className="panel-head"><h2>Worksheet</h2></div>
        <div className="panel-body">
          <label>SQL<textarea value={sql} spellCheck={false} maxLength={SQL_LIMIT} readOnly={running}
            onChange={event => setSql(event.target.value)} rows={8} /></label>
          <div className="pipeline-actions">
            <button type="button" className="button primary" disabled={running || !snapshot?.batch || !sql.trim()} onClick={() => void run()}>Run query</button>
            {running && <button type="button" className="button" onClick={() => { job.current?.abort(); setRunning(false); setQueryError('Query stopped.') }}>Stop</button>}
            {running && <p role="status" className="muted">Running query…</p>}
          </div>
          <form className="workbench-tools" onSubmit={save}>
            <label>Query name<input value={name} onChange={event => setName(event.target.value)} maxLength={64} required /></label>
            <button className="button" disabled={saving || running || !name.trim() || !sql.trim()}>Save query</button>
          </form>
          {savedNotice && <p role="status" className="muted">{savedNotice}</p>}
          {saveError && <p role="alert" className="feedback">{saveError}</p>}
          {queryError && <p role="alert" className="feedback worksheet-error">{queryError}</p>}
          {result && <>
            <p role="status" className="muted">{result.truncated ? 'Showing the first 200 rows.' : result.rows.length + ' result rows'}</p>
            <DataGrid name="Query results" columns={result.columns} rows={result.rows} empty="No rows matched this query." />
          </>}
        </div>
      </section>
    </div>
  </>
}
