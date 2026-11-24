export type Cell = string | number | boolean | null

const numeric = new Set(['amount', 'revenue', 'order_count', 'row_no', 'valid rows'])

export function DataGrid({ name, columns, rows, empty }: {
  name: string
  columns: string[]
  rows: Cell[][]
  empty: string
}) {
  if (!rows.length) return <p className="panel-empty muted">{empty}</p>
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={name}>
      <table aria-label={name}>
        <thead><tr>{columns.map(column => <th scope="col" key={column} className={numeric.has(column.toLowerCase()) ? 'numeric' : undefined}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={index}>{row.map((value, column) => (
            <td key={columns[column]} className={numeric.has(columns[column].toLowerCase()) ? 'numeric' : undefined}>
              {value === null ? '—' : String(value)}
            </td>
          ))}</tr>
        ))}</tbody>
      </table>
    </div>
  )
}
