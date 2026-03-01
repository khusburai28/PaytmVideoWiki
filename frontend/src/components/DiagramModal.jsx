import { useState } from 'react'
import CloseIcon from '@mui/icons-material/Close'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import Mermaid from 'react-mermaid2'
import './DiagramModal.css'

function DiagramModal({ isOpen, onClose, onGenerate, videoName, isGenerating, diagramData }) {
  const [query, setQuery] = useState('')

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
            Generate Diagram
          </h3>
          <button className="modal-close-btn" onClick={handleClose}>
            <CloseIcon sx={{ fontSize: '1.2rem' }} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-description">
            Generate a visual diagram from <strong>{videoName}</strong>
          </p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="diagram-query">
                What would you like to visualize?
              </label>
              <textarea
                id="diagram-query"
                className="modal-textarea"
                placeholder="e.g., Show the system architecture, Create a flowchart of the process, Visualize the component relationships..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={3}
                disabled={isGenerating}
                required
              />
              <p className="form-hint">
                Describe what you want to see in the diagram
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
                {isGenerating ? 'Generating...' : 'Generate Diagram'}
              </button>
            </div>
          </form>

          {/* Diagram Display */}
          {diagramData && (
            <div className="diagram-container">
              <div className="diagram-header">
                <h4>Generated Diagram</h4>
              </div>
              <div className="diagram-content">
                <Mermaid chart={diagramData} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DiagramModal
