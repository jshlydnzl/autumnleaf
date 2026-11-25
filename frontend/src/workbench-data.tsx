import { useEffect, useState } from 'react'
import { message, read } from './api'

export type Selection = { month: string, mode: 'elt' | 'etl' }
export type ReportSelection = Selection & { from?: string, to?: string }
export type Report = {
  month: string
  mode: Selection['mode']
  batch: string | null
  daily: [date: string, count: number, revenue: string][]
  order_count: number
  revenue: string
}
export type Snapshot = Report & { orders: [id: string, date: string, amount: string][] }

export function currentSelection(): Selection {
  const today = new Date()
  return { month: today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0'), mode: 'elt' }
}

export function selectionParams({ month, mode, from, to }: ReportSelection) {
  const params = new URLSearchParams({ month, mode })
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  return params
}

export function useSelectionData<T>(path: string, selection: ReportSelection, revision = 0) {
  const query = selectionParams(selection).toString()
  const key = path + '?' + query + ':' + revision
  const valid = /^\d{4}-\d{2}$/.test(selection.month)
  const [state, setState] = useState<{ key: string, data?: T, error?: string }>({ key: '' })
  useEffect(() => {
    if (!valid) return
    const controller = new AbortController()
    read<T>(path + '?' + query, controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ key, data }) })
      .catch(err => { if (!controller.signal.aborted) setState({ key, error: message(err) }) })
    return () => controller.abort()
  }, [key, path, query, valid])
  return { current: valid && state.key === key ? state : null, loading: valid && state.key !== key }
}

export function BatchFilters({ selection, onChange }: {
  selection: Selection, onChange: (selection: Selection) => void,
}) {
  return <div className="workbench-filters" aria-label="Published batch">
    <label>Batch month<input type="month" value={selection.month}
      onChange={event => onChange({ ...selection, month: event.target.value })} /></label>
    <label>Pipeline mode<select value={selection.mode}
      onChange={event => onChange({ ...selection, mode: event.target.value === 'etl' ? 'etl' : 'elt' })}>
      <option value="elt">ELT</option><option value="etl">ETL</option>
    </select></label>
  </div>
}
