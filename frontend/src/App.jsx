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
        <h1>Video RAG</h1>
        <p>Chat with your videos using AI</p>
      </header>

      <div className="app-container">
        {!currentVideo ? (
          <div className="upload-section">
            <UploadVideo onVideoUploaded={handleVideoUploaded} />

            {videos.length > 0 && (
              <div className="video-list">
                <h2>Previously Uploaded Videos</h2>
                <div className="video-grid">
                  {videos.map(video => (
                    <div
                      key={video.video_id}
                      className="video-card"
                      onClick={() => setCurrentVideo(video)}
                    >
                      <div className="video-card-content">
                        <h3>{video.filename}</h3>
                        <p>{video.total_segments} segments</p>
                        <p className="video-date">
                          {new Date(video.upload_date).toLocaleDateString()}
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
              <button
                className="back-button"
                onClick={() => setCurrentVideo(null)}
              >
                ← Back to Videos
              </button>
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
    </div>
  )
}

export default App
