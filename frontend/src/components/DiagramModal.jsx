import { useState } from 'react'
import CloseIcon from '@mui/icons-material/Close'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import Mermaid from 'react-mermaid2'
import './DiagramModal.css'

function DiagramModal({ isOpen, onClose, onGenerate, videoName, isGenerating, diagramData }) {
  const [query, setQuery] = useState('')
  const [renderError, setRenderError] = useState(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      onGenerate(query)
    }
  }

  const handleClose = () => {
    setQuery('')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content diagram-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <AccountTreeIcon sx={{ fontSize: '1.2rem' }} />
            Generate Knowledge Graph
          </h3>
          <button className="modal-close-btn" onClick={handleClose}>
            <CloseIcon sx={{ fontSize: '1.2rem' }} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-description">
            Generate an asset relationship, process flow, or RCA graph from <strong>{videoName}</strong>
          </p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="diagram-query">
                What operational relationship should be visualized?
              </label>
              <textarea
                id="diagram-query"
                className="modal-textarea"
                placeholder="e.g., Map asset tags to failure modes, show the shutdown workflow, visualize inspection findings and RCA hypotheses..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={3}
                disabled={isGenerating}
                required
              />
              <p className="form-hint">
                Describe the asset, process, compliance, or incident relationship you want to see
              </p>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn-cancel"
                onClick={handleClose}
                disabled={isGenerating}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="modal-btn-primary"
                disabled={isGenerating || !query.trim()}
              >
                <AccountTreeIcon sx={{ fontSize: '1rem' }} />
                {isGenerating ? 'Generating...' : 'Generate Graph'}
              </button>
            </div>
          </form>

          {/* Diagram Display */}
          {diagramData && (
            <div className="diagram-container">
              <div className="diagram-header">
                <h4>Generated Knowledge Graph</h4>
              </div>
              <div className="diagram-content">
                {renderError ? (
                  <div className="diagram-error">
                    <p>Failed to render diagram</p>
                    <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>Error: {renderError}</p>
                    <details style={{ marginTop: '1rem' }}>
                      <summary>Diagram Code</summary>
                      <pre style={{ fontSize: '0.85rem', overflow: 'auto' }}>{diagramData}</pre>
                    </details>
                  </div>
                ) : (
                  <Mermaid
                    chart={diagramData}
                    onError={(error) => {
                      console.error('Mermaid render error:', error)
                      setRenderError(error.message || 'Unknown error')
                    }}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DiagramModal
