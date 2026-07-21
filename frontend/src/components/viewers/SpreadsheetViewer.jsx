import { useState, useEffect } from 'react'
import { apiGet } from '../../utils/api'
import './SpreadsheetViewer.css'

function SpreadsheetViewer({ documentId }) {
  const [sheets, setSheets] = useState(null)
  const [activeSheet, setActiveSheet] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    apiGet(`/api/document/${documentId}/preview`)
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load preview')
        const data = await res.json()
        if (cancelled) return
        setSheets(data)
        setActiveSheet(Object.keys(data)[0] || null)
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))

    return () => { cancelled = true }
  }, [documentId])

  if (loading) return <div className="spreadsheet-viewer-status">Loading preview...</div>
  if (error) return <div className="spreadsheet-viewer-status">Could not load spreadsheet preview.</div>
  if (!sheets || !activeSheet) return <div className="spreadsheet-viewer-status">No data to preview.</div>

  const sheet = sheets[activeSheet]

  return (
    <div className="spreadsheet-viewer-container">
      {Object.keys(sheets).length > 1 && (
        <div className="sheet-tabs">
          {Object.keys(sheets).map((name) => (
            <button
              key={name}
              className={`sheet-tab ${name === activeSheet ? 'active' : ''}`}
              onClick={() => setActiveSheet(name)}
            >
              {name}
            </button>
          ))}
        </div>
      )}
      <div className="spreadsheet-table-scroll">
        <table className="spreadsheet-table">
          <thead>
            <tr>
              {sheet.columns.map((col, i) => (
                <th key={i}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sheet.total_rows > sheet.rows.length && (
        <p className="spreadsheet-truncated-hint">
          Showing {sheet.rows.length} of {sheet.total_rows} rows. Ask the copilot to search the full sheet.
        </p>
      )}
    </div>
  )
}

export default SpreadsheetViewer
