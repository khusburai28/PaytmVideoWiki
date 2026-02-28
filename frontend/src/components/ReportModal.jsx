import { useState } from 'react'
import CloseIcon from '@mui/icons-material/Close'
import DescriptionIcon from '@mui/icons-material/Description'
import './ReportModal.css'

function ReportModal({ isOpen, onClose, onGenerate, videoName, isGenerating }) {
  const [additionalInstructions, setAdditionalInstructions] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    onGenerate(additionalInstructions)
  }

  const handleClose = () => {
    setAdditionalInstructions('')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <DescriptionIcon sx={{ fontSize: '1.2rem' }} />
            Generate Report
          </h3>
          <button className="modal-close-btn" onClick={handleClose}>
            <CloseIcon sx={{ fontSize: '1.2rem' }} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-description">
            Generate a comprehensive PDF report for <strong>{videoName}</strong>
          </p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="instructions">
                Additional Instructions (Optional)
              </label>
              <textarea
                id="instructions"
                className="modal-textarea"
                placeholder="e.g., Focus on security best practices, Include code examples, Highlight deployment steps..."
                value={additionalInstructions}
                onChange={(e) => setAdditionalInstructions(e.target.value)}
                rows={4}
                disabled={isGenerating}
              />
              <p className="form-hint">
                Add any specific topics or areas you'd like the report to focus on
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
                disabled={isGenerating}
              >
                <DescriptionIcon sx={{ fontSize: '1rem' }} />
                {isGenerating ? 'Generating...' : 'Generate Report'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default ReportModal
