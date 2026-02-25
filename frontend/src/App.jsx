import { useState, useEffect } from 'react'
import VideoPlayer from './components/VideoPlayer'
import ChatInterface from './components/ChatInterface'
import UploadVideo from './components/UploadVideo'
import './App.css'

function App() {
  const [currentVideo, setCurrentVideo] = useState(null)
  const [videoTime, setVideoTime] = useState(0)
  const [videos, setVideos] = useState([])

  const handleVideoUploaded = (videoInfo) => {
    setCurrentVideo(videoInfo)
    loadVideos()
  }

  const handleTimestampClick = (timestamp) => {
    setVideoTime(timestamp)
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
            <img src="/logo.svg" alt="Paytm Logo" className="paytm-logo-img" />
            <div style={{ borderLeft: '2px solid #E0E0E0', height: '30px', margin: '0 0.5rem' }}></div>
            <div>
              <h1>Knowledge Transfer Hub</h1>
              <p>Your onboarding & learning companion</p>
            </div>
          </div>
        </div>
      </header>

      <div className="app-container">
        {!currentVideo ? (
          <div className="upload-section">
            <UploadVideo onVideoUploaded={handleVideoUploaded} />

            {videos.length > 0 && (
              <div className="video-list">
                <h2>📚 KT Video Library</h2>
                <div className="video-grid">
                  {videos.map(video => (
                    <div
                      key={video.video_id}
                      className="video-card"
                      onClick={() => setCurrentVideo(video)}
                    >
                      <div className="video-card-thumbnail">
                        🎥
                      </div>
                      <div className="video-card-content">
                        <h3>{video.filename}</h3>
                        <div className="video-card-meta">
                          <span className="video-badge">
                            📊 {video.total_segments} segments
                          </span>
                        </div>
                        <p className="video-date">
                          Uploaded {new Date(video.upload_date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric'
                          })}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="main-interface">
            <div className="video-section">
              <div className="video-header">
                <button
                  className="back-button"
                  onClick={() => setCurrentVideo(null)}
                >
                  ← Library
                </button>
                <h3 style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', margin: 0 }}>
                  {currentVideo.filename}
                </h3>
              </div>
              <VideoPlayer
                videoId={currentVideo.video_id}
                seekTime={videoTime}
              />
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

      <footer className="paytm-footer">
        <div className="footer-stripe"></div>
      </footer>
    </div>
  )
}

export default App
