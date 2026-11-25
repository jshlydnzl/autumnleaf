import { useEffect, useState, type ReactNode } from 'react'
import { message, read, write } from './api'
import { DataGrid } from './data-grid'

type Dataset = { id: string, title: string, sample_month: string, url: string }
type Category = { id: string, title: string, datasets: Dataset[] }
type Preview = { checksum: string, rows: string[][], total: number }
type SourceProps<Run> = {
  mode: 'elt' | 'etl', busy: boolean,
  onMode: (mode: 'elt' | 'etl') => void,
  onRun: (run: Run, reused: boolean) => void,
}

export function PipelineInput<Run>({ children, ...props }: SourceProps<Run> & { children: ReactNode }) {
  const [source, setSource] = useState('file')
  return <>
    <div className="panel pipeline-form">
      <label>Source<select value={source} disabled={props.busy} onChange={event => setSource(event.target.value)}>
        <option value="file">Upload CSV</option><option value="kaggle">Kaggle</option>
      </select></label>
    </div>
    {source === 'kaggle' ? <KaggleSource {...props} /> : children}
  </>
}

function KaggleSource<Run>({ mode, busy, onMode, onRun }: SourceProps<Run>) {
  const [catalog, setCatalog] = useState<Category[] | null>(null)
  const [categoryId, setCategoryId] = useState('')
  const [datasetId, setDatasetId] = useState('')
  const [month, setMonth] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    read<{ categories: Category[] }>('pipelines/kaggle/catalog/', controller.signal)
      .then(({ categories }) => { if (!controller.signal.aborted) setCatalog(categories) })
      .catch(err => { if (!controller.signal.aborted) setError(message(err)) })
    return () => controller.abort()
  }, [])

  const datasets = catalog?.find(item => item.id === categoryId)?.datasets ?? []
  const dataset = datasets.find(item => item.id === datasetId)
  const locked = busy || pending

  function clearPreview() {
    setPreview(null)
    setError('')
  }

  async function request(importBatch: boolean) {
    if (!dataset || !month || locked || (importBatch && !preview)) return
    setPending(true)
    setError('')
    const path = 'pipelines/kaggle/import/'
    const data = { dataset: dataset.id, month }
    try {
      if (importBatch && preview) {
        const result = await write<{ run: Run, reused: boolean }>(path, 'POST', { ...data, mode, checksum: preview.checksum })
        onRun(result.run, result.reused)
      } else {
        setPreview(null)
        setPreview(await write<Preview>(path, 'POST', data))
      }
    } catch (err) {
      setError(message(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="panel kaggle-panel" aria-labelledby="kaggle-source-title">
      <div className="panel-head"><h2 id="kaggle-source-title">Kaggle dataset</h2></div>
      <div className="panel-body">
        {!catalog && !error && <p role="status">Loading datasets…</p>}
        <div className="kaggle-controls">
          <label>Category<select value={categoryId} disabled={locked || !catalog} onChange={event => {
            clearPreview()
            setCategoryId(event.target.value)
            setDatasetId('')
            setMonth('')
          }}>
            <option value="">Choose a category</option>
            {catalog?.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select></label>
          <label>Dataset<select value={datasetId} disabled={locked || !categoryId} onChange={event => {
            clearPreview()
            setDatasetId(event.target.value)
            setMonth(datasets.find(item => item.id === event.target.value)?.sample_month ?? '')
          }}>
            <option value="">Choose a dataset</option>
            {datasets.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select></label>
          <label>Batch month<input type="month" value={month} disabled={locked || !dataset} onChange={event => {
            clearPreview()
            setMonth(event.target.value)
          }} /></label>
          <label>Pipeline mode<select value={mode} disabled={locked} onChange={event => onMode(event.target.value === 'etl' ? 'etl' : 'elt')}>
            <option value="elt">ELT · SQL transform</option><option value="etl">ETL · Python transform</option>
          </select></label>
          <button type="button" className="button" disabled={locked || !dataset || !month} onClick={() => void request(false)}>Preview dataset</button>
        </div>
        {dataset && <p className="muted"><a className="text-link" href={dataset.url} target="_blank" rel="noreferrer">View dataset on Kaggle</a>. Amounts are for testing; no currency conversion is applied.</p>}
        {pending && <p role="status">Fetching the selected Kaggle file…</p>}
        {error && <p className="feedback pipeline-feedback" role="alert">{error}</p>}
        {preview && <>
          <p className="muted">{preview.total} orders in the selected month. Only order IDs, dates, and amounts will be imported.</p>
          <DataGrid name="Kaggle order preview" columns={['Order ID', 'Date', 'Amount']} rows={preview.rows} empty="" />
          <button type="button" className="button primary" disabled={locked} onClick={() => void request(true)}>Create {mode.toUpperCase()} run</button>
        </>}
      </div>
    </section>
  )
}
