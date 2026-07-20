import { useState } from 'react'
import WarningIcon from '@mui/icons-material/Warning'
import SettingsIcon from '@mui/icons-material/Settings'
import AudiotrackIcon from '@mui/icons-material/Audiotrack'
import MicIcon from '@mui/icons-material/Mic'
import DataUsageIcon from '@mui/icons-material/DataUsage'
import SearchIcon from '@mui/icons-material/Search'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import { apiPost, apiGet } from '../utils/api'
import './UploadVideo.css'

function UploadVideo({ onVideoUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [error, setError] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [videoName, setVideoName] = useState('')
  const [videoDescription, setVideoDescription] = useState('')
  const [showForm, setShowForm] = useState(false)

  const handleFileSelected = (file) => {
    if (!file) return

    // Validate file type
    const validTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 'video/webm']
    if (!validTypes.includes(file.type)) {
      setError('Invalid file type. Please upload MP4, AVI, MOV, MKV, or WEBM evidence.')
      return
    }

    setSelectedFile(file)
    setShowForm(true)
    setError(null)
  }

  const handleUpload = async (e) => {
    e.preventDefault()

    if (!selectedFile || !videoName.trim() || !videoDescription.trim()) {
      setError('Please fill in all fields')
      return
    }

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('name', videoName)
      formData.append('description', videoDescription)

      const response = await apiPost('/api/upload', formData)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data = await response.json()
      setUploading(false)
      setProcessing(true)

      // Poll for processing status
      pollStatus(data.video_id)

    } catch (err) {
      setError(err.message)
      setUploading(false)
    }
  }

  const pollStatus = async (videoId) => {
    const interval = setInterval(async () => {
      try {
        const response = await apiGet(`/api/status/${videoId}`)
        const data = await response.json()

        setProgress(data.progress)
        setStatusMessage(data.message || 'Processing...')

        if (data.status === 'completed') {
          clearInterval(interval)
          setProcessing(false)
          setStatusMessage('')

          // Fetch video info
          const videoResponse = await apiGet(`/api/videos`)
          const videos = await videoResponse.json()
          const video = videos.find(v => v.video_id === videoId)

          if (video) {
            onVideoUploaded(video)
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
    setVideoName('')
    setVideoDescription('')
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
            id="video-upload"
            accept="video/*"
            onChange={handleFileInput}
            style={{ display: 'none' }}
          />
          <div className="upload-icon">
            <DataUsageIcon sx={{ fontSize: '4rem' }} />
          </div>
          <p className="upload-text">
            Drop a field walkthrough, inspection recording, or operator briefing here, or{' '}
            <label htmlFor="video-upload" className="upload-link">
              browse
            </label>
          </p>
          <p className="upload-hint">
            Current demo supports video evidence: MP4, AVI, MOV, MKV, WEBM (max 5GB)
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
            <label htmlFor="video-name">Asset / Evidence Title *</label>
            <input
              type="text"
              id="video-name"
              value={videoName}
              onChange={(e) => setVideoName(e.target.value)}
              placeholder="e.g., Boiler B-102 annual shutdown inspection"
              maxLength={200}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="video-description">Operational Context *</label>
            <textarea
              id="video-description"
              value={videoDescription}
              onChange={(e) => setVideoDescription(e.target.value)}
              placeholder="Mention asset tags, area, failure mode, inspection scope, safety constraints, or compliance references..."
              rows={4}
              maxLength={1000}
              required
            />
            <span className="char-count">{videoDescription.length}/1000</span>
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
              <div className={`stage ${progress >= 10 ? 'completed' : ''} ${progress < 10 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <SettingsIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Initializing</span>
              </div>
              <div className={`stage ${progress >= 20 ? 'completed' : ''} ${progress >= 10 && progress < 40 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <AudiotrackIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Extracting Signals</span>
              </div>
              <div className={`stage ${progress >= 70 ? 'completed' : ''} ${progress >= 40 && progress < 70 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <MicIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Transcribing Evidence</span>
              </div>
              <div className={`stage ${progress >= 85 ? 'completed' : ''} ${progress >= 70 && progress < 85 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <DataUsageIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Building Context</span>
              </div>
              <div className={`stage ${progress >= 95 ? 'completed' : ''} ${progress >= 85 && progress < 95 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <SearchIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Graph Indexing</span>
              </div>
              <div className={`stage ${progress === 100 ? 'completed' : ''} ${progress >= 95 && progress < 100 ? 'active' : ''}`}>
                <span className="stage-icon">
                  <CheckCircleIcon sx={{ fontSize: '2rem' }} />
                </span>
                <span className="stage-label">Finalizing</span>
              </div>
            </div>
            <p className="upload-hint">
              This may take 2-5 minutes depending on evidence length
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

      <div className="info-section">
        <h3>Industrial Intelligence Workflow</h3>
        <ol>
          <li>Ingest videos today, then extend the same pipeline to PDFs, P&IDs, work orders, spreadsheets, and emails.</li>
          <li>Extract asset tags, failure modes, process parameters, people, dates, and regulatory references.</li>
          <li>Build a searchable knowledge layer with citations, timestamps, and confidence-aware answers.</li>
          <li>Generate RCA briefs, maintenance recommendations, compliance evidence packs, and lessons learned.</li>
          <li>Serve field technicians, engineers, quality teams, and auditors from the same operational memory.</li>
        </ol>
      </div>
    </div>
  )
}

export default UploadVideo
