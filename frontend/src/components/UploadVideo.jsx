import { useState } from 'react'
import './UploadVideo.css'

function UploadVideo({ onVideoUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const [dragActive, setDragActive] = useState(false)

  const handleUpload = async (file) => {
    if (!file) return

    // Validate file type
    const validTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 'video/webm']
    if (!validTypes.includes(file.type)) {
      setError('Invalid file type. Please upload MP4, AVI, MOV, MKV, or WEBM.')
      return
    }

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

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
        const response = await fetch(`/api/status/${videoId}`)
        const data = await response.json()

        setProgress(data.progress)

        if (data.status === 'completed') {
          clearInterval(interval)
          setProcessing(false)

          // Fetch video info
          const videoResponse = await fetch(`/api/videos`)
          const videos = await videoResponse.json()
          const video = videos.find(v => v.video_id === videoId)

          if (video) {
            onVideoUploaded(video)
          }
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setProcessing(false)
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
      handleUpload(e.dataTransfer.files[0])
    }
  }

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleUpload(e.target.files[0])
    }
  }

  return (
    <div className="upload-container">
      <h2>Upload Knowledge Transfer Video</h2>

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
          disabled={uploading || processing}
          style={{ display: 'none' }}
        />

        {!uploading && !processing ? (
          <>
            <div className="upload-icon">📹</div>
            <p className="upload-text">
              Drag and drop your KT video here, or{' '}
              <label htmlFor="video-upload" className="upload-link">
                browse
              </label>
            </p>
            <p className="upload-hint">
              Supported formats: MP4, AVI, MOV, MKV, WEBM (max 5GB)
            </p>
          </>
        ) : uploading ? (
          <>
            <div className="loading-spinner"></div>
            <p className="upload-text">Uploading KT video...</p>
          </>
        ) : (
          <>
            <div className="loading-spinner"></div>
            <p className="upload-text">Processing video for AI search...</p>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }}></div>
            </div>
            <p className="progress-text">{progress}%</p>
            <p className="upload-hint">
              Transcribing and indexing content (2-5 minutes)
            </p>
          </>
        )}
      </div>

      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
        </div>
      )}

      <div className="info-section">
        <h3>🎓 For Developers & New Joiners</h3>
        <ol>
          <li>Upload your KT video securely to Paytm's platform</li>
          <li>AI transcribes and indexes the content automatically</li>
          <li>Ask questions about the video and get instant answers</li>
          <li>Jump to specific topics with clickable timestamps</li>
          <li>Perfect for onboarding, training, and knowledge sharing</li>
        </ol>
      </div>
    </div>
  )
}

export default UploadVideo
