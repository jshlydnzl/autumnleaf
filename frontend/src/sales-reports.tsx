import { useEffect, useRef, useState } from 'react'
import { BarController, BarElement, CategoryScale, Chart, LinearScale, Tooltip } from 'chart.js'
import { DataGrid } from './data-grid'
import { BatchFilters, currentSelection, selectionParams, useSelectionData, type Report } from './workbench-data'
import './workbench.css'

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

function DailyChart({ daily }: { daily: Report['daily'] }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    if (!canvas.current) return
    const colors = getComputedStyle(canvas.current)
    const text = colors.getPropertyValue('--color-text-muted').trim()
    const bars = new Chart(canvas.current, {
      type: 'bar',
      data: {
        labels: daily.map(([date]) => date),
        datasets: [{ label: 'Revenue', data: daily.map(([, , revenue]) => Number(revenue)),
          backgroundColor: colors.getPropertyValue('--color-primary').trim() }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: { x: { ticks: { color: text, maxTicksLimit: 10 } }, y: { ticks: { color: text }, beginAtZero: true } },
      },
    })
    return () => bars.destroy()
  }, [daily])
  return <div className="sales-chart">
    <canvas ref={canvas} role="img" aria-label="Daily sales revenue. Exact values are in the table below." />
  </div>
}

export default function SalesReports() {
  const [selection, setSelection] = useState(currentSelection)
  const [dates, setDates] = useState({ from: '', to: '' })
  const [revision, setRevision] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const scope = { ...selection, ...dates }
  const { current, loading } = useSelectionData<Report>('analysis/report/', scope, revision)
  const report = current?.data

  async function download() {
    if (!report?.batch || exporting) return
    setExporting(true)
    setExportError('')
    const params = selectionParams(scope)
    params.set('batch', report.batch)
    try {
      const response = await fetch('/api/analysis/export/?' + params)
      if (response.status === 401) window.dispatchEvent(new Event('autumnleaf:session-expired'))
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.error ?? 'The workbook could not be downloaded.')
      }
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = 'sales-' + selection.month + '-' + selection.mode + '.xlsx'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'The workbook could not be downloaded.')
    } finally {
      setExporting(false)
    }
  }

  return <>
    <div className="page-heading">
      <div><p className="eyebrow">Your warehouse</p><h1>Reports</h1><p className="muted">Review published sales and download the same figures as an Excel workbook.</p></div>
      <a className="button" href="/sql">Open SQL Workspace</a>
    </div>
    <section className="panel workbench-tools" aria-label="Report controls">
      <BatchFilters selection={selection} onChange={next => {
        setExportError('')
        if (next.month !== selection.month) setDates({ from: '', to: '' })
        setSelection(next)
      }} />
      <label>From<input type="date" value={dates.from} onChange={event => {
        setExportError('')
        setDates({ ...dates, from: event.target.value })
      }} /></label>
      <label>To<input type="date" value={dates.to} onChange={event => {
        setExportError('')
        setDates({ ...dates, to: event.target.value })
      }} /></label>
      <button type="button" className="button" disabled={loading || !selection.month} onClick={() => { setExportError(''); setRevision(n => n + 1) }}>Refresh report</button>
      <button type="button" className="button primary" disabled={!report?.batch || exporting} onClick={() => void download()}>
        {exporting ? 'Preparing workbook…' : 'Export to Excel'}
      </button>
    </section>
    {(current?.error || exportError) && <p role="alert" className="feedback">{current?.error || exportError}</p>}
    {loading && <p role="status" className="panel-note muted">Loading published sales…</p>}
    {report && !report.batch && <p className="panel panel-empty muted">No published batch for this month and mode.</p>}
    {report?.batch && <section className="panel" aria-label="Published sales">
      <div className="panel-head"><h2>Daily sales</h2><span className="muted">{report.mode.toUpperCase()} · {report.month}</span></div>
      <div className="panel-body">
        <dl className="sales-totals">
          <div><dt>Total revenue</dt><dd>{report.revenue}</dd></div>
          <div><dt>Orders</dt><dd>{report.order_count.toLocaleString()}</dd></div>
        </dl>
        <p className="muted">Amounts are shown as recorded. No currency conversion is applied.</p>
        {report.daily.length > 0 && <DailyChart daily={report.daily} />}
        <DataGrid name="Daily sales report" columns={['Date', 'Order count', 'Revenue']} rows={report.daily} empty="No sales in this batch." />
      </div>
    </section>}
  </>
}
