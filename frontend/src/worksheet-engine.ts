import { AsyncDuckDB, VoidLogger } from '@duckdb/duckdb-wasm'
import moduleUrl from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'
import workerUrl from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url'
import type { Snapshot } from './workbench-data'

export const RESULT_LIMIT = 200
export const SQL_LIMIT = 8000
type Value = string | number | boolean | null
export type WorksheetResult = { columns: string[], rows: Value[][], truncated: boolean }

function csv(rows: (string | number)[][]) {
  return rows.map(row => row.map(value => '"' + String(value).replaceAll('"', '""') + '"').join(',')).join('\n')
}

function display(value: unknown, type: { toString(): string }, scale: number | undefined): Value {
  if (value == null) return null
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') {
    return type.toString().startsWith('Date') ? new Date(value).toISOString().slice(0, 10) : String(value)
  }
  if (scale !== undefined && value instanceof Uint32Array) {
    const integer = BigInt.asIntN(value.length * 32, [...value].reduceRight((n, word) => (n << 32n) | BigInt(word), 0n))
    const raw = integer.toString().replace('-', '').padStart(scale + 1, '0')
    return (integer < 0n ? '-' : '') + (scale ? raw.slice(0, -scale) + '.' + raw.slice(-scale) : raw)
  }
  const text = String(value)
  return text.length > 500 ? text.slice(0, 500) + '…' : text
}

export async function runWorksheet(sql: string, snapshot: Snapshot, signal: AbortSignal): Promise<WorksheetResult> {
  const statement = sql.trim().replace(/;$/, '')
  if (!statement || sql.length > SQL_LIMIT) throw new Error('Enter a query up to 8,000 characters.')
  signal.throwIfAborted()
  const worker = new Worker(workerUrl)
  const db = new AsyncDuckDB(new VoidLogger(), worker)
  let stop = () => {}
  const interrupted = new Promise<never>((_, reject) => {
    stop = () => reject(new DOMException('Query stopped.', 'AbortError'))
    signal.addEventListener('abort', stop, { once: true })
  })
  let timer = 0
  const deadline = new Promise<never>((_, reject) => {
    timer = window.setTimeout(() => reject(new Error('The SQL engine or query took too long. Try a smaller query.')), 15000)
  })

  async function execute() {
    await db.instantiate(moduleUrl)
    await db.open({ maximumThreads: 1, opfs: { fileHandling: 'manual' } })
    const connection = await db.connect()
    await connection.query(`
      CREATE SCHEMA mart;
      CREATE TABLE mart.daily_sales (mode VARCHAR, month DATE, order_date DATE, order_count BIGINT, revenue DECIMAL(18, 2));
      CREATE TABLE mart.orders (order_id VARCHAR, order_date DATE, amount DECIMAL(12, 2));
    `)
    if (snapshot.daily.length) {
      await db.registerFileText('worksheet-daily.csv', csv(snapshot.daily.map(row => [snapshot.mode, snapshot.month + '-01', ...row])))
      await connection.query("COPY mart.daily_sales FROM 'worksheet-daily.csv' (FORMAT CSV, HEADER false)")
      await db.dropFile('worksheet-daily.csv')
    }
    if (snapshot.orders.length) {
      await db.registerFileText('worksheet-orders.csv', csv(snapshot.orders))
      await connection.query("COPY mart.orders FROM 'worksheet-orders.csv' (FORMAT CSV, HEADER false)")
      await db.dropFile('worksheet-orders.csv')
    }
    await connection.query(`
      SET autoload_known_extensions = false;
      SET autoinstall_known_extensions = false;
      SET enable_external_access = false;
      SET memory_limit = '96MB';
      SET lock_configuration = true;
    `)
    // PREPARE accepts one statement. The outer SELECT bounds rows and only accepts a query as its input.
    const prepared = await connection.prepare('SELECT * FROM (\n' + statement + '\n) AS worksheet_result LIMIT ' + (RESULT_LIMIT + 1))
    const table = await prepared.query()
    const fields = table.schema.fields
    if (fields.length > 40) throw new Error('Show at most 40 columns per query.')
    const rows = Array.from({ length: Math.min(table.numRows, RESULT_LIMIT) }, (_, row) => fields.map((field, column) => {
      const scale = 'scale' in field.type && typeof field.type.scale === 'number' ? field.type.scale : undefined
      return display(table.getChildAt(column)?.get(row), field.type, scale)
    }))
    return { columns: fields.map(field => field.name), rows, truncated: table.numRows > RESULT_LIMIT }
  }

  try {
    return await Promise.race([execute(), interrupted, deadline])
  } finally {
    window.clearTimeout(timer)
    signal.removeEventListener('abort', stop)
    worker.terminate()
  }
}
