import { useState, useEffect } from 'react'
import VideoPlayer from './components/VideoPlayer'
import ChatInterface from './components/ChatInterface'
import UploadVideo from './components/UploadVideo'
import VideoSidebar from './components/VideoSidebar'
import DeleteIcon from '@mui/icons-material/Delete'
import DescriptionIcon from '@mui/icons-material/Description'
import './App.css'

function App() {
  const [currentVideo, setCurrentVideo] = useState(null)
  const [videoTime, setVideoTime] = useState(0)
  const [videos, setVideos] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)

  const handleVideoUploaded = (videoInfo) => {
    setCurrentVideo(videoInfo)
    loadVideos()
  }

  const handleTimestampClick = (timestamp) => {
    setVideoTime(timestamp)
  }

  const handleVideoSelect = (video) => {
    setCurrentVideo(video)
  }

  const handleGenerateReport = async (videoId) => {
    setGeneratingReport(true)
    try {
      const response = await fetch(`/api/video/${videoId}/report`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error('Failed to generate report')
      }

      // Get the PDF blob
      const blob = await response.blob()

      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${currentVideo.name || 'video'}_report.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      alert('Report generated successfully!')
    } catch (error) {
      console.error('Failed to generate report:', error)
      alert('Failed to generate report. Please try again.')
    } finally {
      setGeneratingReport(false)
    }
  }

  const handleDeleteVideo = async (videoId) => {
    if (!confirm('Are you sure you want to delete this video? This action cannot be undone.')) {
      return
    }

    try {
      const response = await fetch(`/api/video/${videoId}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Failed to delete video')
      }

      // Clear current video if it was deleted
      if (currentVideo?.video_id === videoId) {
        setCurrentVideo(null)
      }

      // Reload video list
      loadVideos()

      alert('Video deleted successfully')
    } catch (error) {
      console.error('Failed to delete video:', error)
      alert('Failed to delete video. Please try again.')
    }
  }

  const loadVideos = async () => {
    try {
      const response = await fetch('/api/videos')
      const data = await response.json()
      setVideos(data.filter(v => v.status === 'completed'))
    } catch (error) {
      console.error('Failed to load videos:', error)
    }
  }

  useEffect(() => {
    loadVideos()
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-logo">
            {/* <img src="/logo.svg" alt="Paytm Logo" className="paytm-logo-img" />
            <div style={{ borderLeft: '2px solid #E0E0E0', height: '30px', margin: '0 0.5rem' }}></div> */}
            <div>
              <h1>Knowledge Transfer Hub</h1>
              <p>Your onboarding & learning companion</p>
            </div>
          </div>
        </div>
      </header>

      <div className="app-container">
        <VideoSidebar
          videos={videos}
          currentVideo={currentVideo}
          onVideoSelect={handleVideoSelect}
        />

        <div className="main-content">
          {!currentVideo ? (
            <div className="upload-section">
              <UploadVideo onVideoUploaded={handleVideoUploaded} />
            </div>
          ) : (
            <div className="player-interface">
              <div className="video-section">
                <div className="video-header">
                  <div className="video-header-info">
                    <h3 className="video-header-title">
                      {currentVideo.name || currentVideo.filename}
                    </h3>
                    {currentVideo.description && (
                      <p className="video-header-description">
                        {currentVideo.description}
                      </p>
                    )}
                  </div>
                </div>
                <VideoPlayer
                  videoId={currentVideo.video_id}
                  seekTime={videoTime}
                />
                <div className="video-actions">
                  <button
                    className="generate-report-btn"
                    onClick={() => handleGenerateReport(currentVideo.video_id)}
                    disabled={generatingReport}
                  >
                    <DescriptionIcon sx={{ fontSize: '1.1rem' }} />
                    {generatingReport ? 'Generating...' : 'Generate Report'}
                  </button>
                  <button
                    className="delete-video-btn"
                    onClick={() => handleDeleteVideo(currentVideo.video_id)}
                    disabled={generatingReport}
                  >
                    <DeleteIcon sx={{ fontSize: '1.1rem' }} />
                    Delete Video
                  </button>
                </div>
              </div>

              <div className="chat-section">
                <ChatInterface
                  videoId={currentVideo.video_id}
                  onTimestampClick={handleTimestampClick}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* <footer className="paytm-footer">
        <div className="footer-stripe"></div>
      </footer> */}
    </div>
  )
}

export default App
