import { useState } from 'react'
import WarningIcon from '@mui/icons-material/Warning'
import SettingsIcon from '@mui/icons-material/Settings'
import FindInPageIcon from '@mui/icons-material/FindInPage'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import DataUsageIcon from '@mui/icons-material/DataUsage'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import { apiPost, apiGet } from '../utils/api'
import './UploadDocument.css'

const VALID_TYPES = [
  'video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 'video/webm',
  'application/pdf',
  'image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/webp',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'text/csv',
]

const VALID_EXTENSIONS = /\.(mp4|avi|mov|mkv|webm|pdf|png|jpe?g|gif|bmp|webp|xlsx|xls|csv)$/i

function UploadDocument({ onDocumentUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [error, setError] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [documentName, setDocumentName] = useState('')
  const [documentDescription, setDocumentDescription] = useState('')
  const [showForm, setShowForm] = useState(false)

  const handleFileSelected = (file) => {
    if (!file) return

    const validByType = VALID_TYPES.includes(file.type)
    const validByExtension = VALID_EXTENSIONS.test(file.name)
    if (!validByType && !validByExtension) {
      setError('Unsupported file type. Upload a video, PDF, image, or spreadsheet (XLSX/XLS/CSV).')
      return
    }

    setSelectedFile(file)
    setShowForm(true)
    setError(null)
  }

  const handleUpload = async (e) => {
    e.preventDefault()

    if (!selectedFile || !documentName.trim() || !documentDescription.trim()) {
      setError('Please fill in all fields')
      return
    }

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('name', documentName)
      formData.append('description', documentDescription)

      const response = await apiPost('/api/upload', formData)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data = await response.json()
      setUploading(false)
      setProcessing(true)

      pollStatus(data.document_id)

    } catch (err) {
      setError(err.message)
      setUploading(false)
    }
  }

  const pollStatus = async (documentId) => {
    const interval = setInterval(async () => {
      try {
        const response = await apiGet(`/api/status/${documentId}`)
        const data = await response.json()

        setProgress(data.progress)
        setStatusMessage(data.message || 'Processing...')

        if (data.status === 'completed') {
          clearInterval(interval)
          setProcessing(false)
          setStatusMessage('')

          const docsResponse = await apiGet(`/api/documents`)
          const documents = await docsResponse.json()
          const doc = documents.find(d => d.document_id === documentId)

          if (doc) {
            onDocumentUploaded(doc)
          }
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setProcessing(false)
          setStatusMessage('')
          setError(data.message || 'Processing failed')
        }
      } catch (err) {
        console.error('Status check failed:', err)
      }
    }, 2000)
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0])
    }
  }

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0])
    }
  }

  const handleCancel = () => {
    setSelectedFile(null)
    setDocumentName('')
    setDocumentDescription('')
    setShowForm(false)
    setError(null)
  }

  return (
    <div className="upload-container">
      <h2>Ingest Industrial Knowledge Evidence</h2>

      {!showForm && !uploading && !processing ? (
        <div
          className={`drop-zone ${dragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="document-upload"
            accept="video/*,application/pdf,image/*,.xlsx,.xls,.csv"
            onChange={handleFileInput}
            style={{ display: 'none' }}
          />
          <div className="upload-icon">
            <DataUsageIcon sx={{ fontSize: '4rem' }} />
          </div>
          <p className="upload-text">
            Drop a video, PDF, drawing, photo, or spreadsheet here, or{' '}
            <label htmlFor="document-upload" className="upload-link">
              browse
            </label>
          </p>
          <p className="upload-hint">
            Supports video (MP4/AVI/MOV/MKV/WEBM), PDF, images (PNG/JPG), and spreadsheets (XLSX/CSV) — max 5GB
          </p>
        </div>
      ) : showForm && !uploading && !processing ? (
        <form onSubmit={handleUpload} className="video-metadata-form">
          <div className="selected-file">
            <span className="file-icon">
              <DataUsageIcon sx={{ fontSize: '1.4rem' }} />
            </span>
            <span className="file-name">{selectedFile?.name}</span>
          </div>

          <div className="form-group">
            <label htmlFor="document-name">Asset / Evidence Title *</label>
            <input
              type="text"
              id="document-name"
              value={documentName}
              onChange={(e) => setDocumentName(e.target.value)}
              placeholder="e.g., Boiler B-102 annual shutdown inspection"
              maxLength={200}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="document-description">Operational Context *</label>
            <textarea
              id="document-description"
              value={documentDescription}
              onChange={(e) => setDocumentDescription(e.target.value)}
              placeholder="Mention asset tags, area, failure mode, inspection scope, safety constraints, or compliance references..."
              rows={4}
              maxLength={1000}
              required
            />
            <span className="char-count">{documentDescription.length}/1000</span>
          </div>

          <div className="form-actions">
            <button type="button" onClick={handleCancel} className="btn-cancel">
              Cancel
            </button>
            <button type="submit" className="btn-upload">
              Ingest & Index
            </button>
          </div>
        </form>
      ) : uploading ? (
        <div className="upload-status">
          <div className="loading-spinner"></div>
          <p className="upload-text">Uploading operational evidence...</p>
          <p className="upload-hint">The asset brain will start indexing as soon as upload completes</p>
        </div>
      ) : (
        <div className="upload-status">
          <div className="loading-spinner"></div>
          <div className="status-details">
            <p className="upload-text">{statusMessage || 'Processing operational evidence...'}</p>
            <div className="progress-container">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }}></div>
              </div>
              <p className="progress-text">{progress}%</p>
            </div>
            <div className="processing-stages">
              <div className={`stage ${progress >= 20 ? 'completed' : ''} ${progress < 20 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <SettingsIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Initializing</span>
              </div>
              <div className={`stage ${progress >= 70 ? 'completed' : ''} ${progress >= 20 && progress < 70 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <FindInPageIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Reading Content</span>
              </div>
              <div className={`stage ${progress >= 85 ? 'completed' : ''} ${progress >= 70 && progress < 85 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <AutoAwesomeIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Indexing Chunks</span>
              </div>
              <div className={`stage ${progress >= 95 ? 'completed' : ''} ${progress >= 85 && progress < 95 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <AccountTreeIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Building Knowledge Graph</span>
              </div>
              <div className={`stage ${progress === 100 ? 'completed' : ''} ${progress >= 95 && progress < 100 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <CheckCircleIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Finalizing</span>
              </div>
            </div>
            <p className="upload-hint">
              This may take a few seconds to a few minutes depending on file size and type
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="error-message">
          <span className="error-icon">
            <WarningIcon sx={{ fontSize: '1.2rem' }} />
          </span>
          {error}
        </div>
      )}

    </div>
  )
}

export default UploadDocument
