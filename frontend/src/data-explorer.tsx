import { useEffect, useState } from 'react'
import { message, read } from './api'
import { DataGrid, type Cell } from './data-grid'

type Table = {
  tables: string[]
  table: string
  columns: [string, string][]
  rows: Cell[][]
  total: number
}

const tables = [
  ['raw.orders', 'Original rows loaded by ELT. Includes runs that failed validation.'],
  ['staging.orders', 'Validated rows, including batches awaiting replacement approval.'],
  ['mart.daily_sales', 'Daily sales from the currently published batches, separated by pipeline mode.'],
]

export function DataExplorer() {
  const [active, setActive] = useState('mart.daily_sales')
  const [offset, setOffset] = useState(0)
  const [result, setResult] = useState<Table | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    read<Table>('warehouse/?' + new URLSearchParams({ table: active, offset: String(offset) }), controller.signal)
      .then(data => { if (!controller.signal.aborted) setResult(data) })
      .catch(err => { if (!controller.signal.aborted) setError(message(err)) })
    return () => controller.abort()
  }, [active, offset])

  function open(table: string, next = 0) {
    if (table === active && next === offset) return
    setResult(null)
    setError('')
    setActive(table)
    setOffset(next)
  }

  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">Your warehouse</p><h1>Data Explorer</h1><p className="muted">Inspect the tables in your private DuckDB workspace.</p></div>
        <a className="button" href="/pipelines">Open Pipeline Lab</a>
      </div>
      <div className="explorer-grid">
        <aside className="panel table-tree">
          <div className="panel-head"><h2>Tables</h2></div>
          {tables.map(([table]) => <button key={table} type="button" aria-pressed={active === table} onClick={() => open(table)}>{table}</button>)}
        </aside>
        <section className="panel warehouse-preview" aria-labelledby="table-name">
          <div className="panel-head"><h2 id="table-name">{active}</h2><span className="muted">{result ? result.total + ' rows' : ''}</span></div>
          <p className="panel-note muted">{tables.find(([table]) => table === active)?.[1]}</p>
          {error ? <p className="feedback" role="alert">{error}</p>
            : result ? (
              <>
                <details className="table-schema">
                  <summary>Columns and types</summary>
                  <dl>{result.columns.map(([column, type]) => <div key={column}><dt>{column}</dt><dd>{type}</dd></div>)}</dl>
                </details>
                <DataGrid name={active + ' preview'} columns={result.columns.map(([column]) => column)} rows={result.rows} empty="No rows in this table yet." />
                {result.total > 25 && <div className="pager">
                  <button className="button" type="button" disabled={!offset} onClick={() => open(active, offset - 25)}>Previous</button>
                  <span className="muted">{offset + 1}–{offset + result.rows.length} of {result.total}</span>
                  <button className="button" type="button" disabled={offset + 25 >= result.total} onClick={() => open(active, offset + 25)}>Next</button>
                </div>}
              </>
            ) : <p className="panel-empty muted" role="status">Loading table…</p>}
        </section>
      </div>
    </>
  )
}
