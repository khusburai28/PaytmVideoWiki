import { useState, useEffect } from 'react'
import VideoPlayer from './components/VideoPlayer'
import ChatInterface from './components/ChatInterface'
import UploadVideo from './components/UploadVideo'
import VideoSidebar from './components/VideoSidebar'
import Login from './components/Login'
import AdminPanel from './components/AdminPanel'
import DeleteIcon from '@mui/icons-material/Delete'
import DescriptionIcon from '@mui/icons-material/Description'
import LogoutIcon from '@mui/icons-material/Logout'
import GroupsIcon from '@mui/icons-material/Groups'
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary'
import PersonIcon from '@mui/icons-material/Person'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import CloseIcon from '@mui/icons-material/Close'
import { apiGet, apiPost, apiDelete } from './utils/api'
import './App.css'

function App() {
  const [currentVideo, setCurrentVideo] = useState(null)
  const [videoTime, setVideoTime] = useState(0)
  const [videos, setVideos] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [currentView, setCurrentView] = useState('videos') // 'videos' or 'admin'
  const [showAIPanel, setShowAIPanel] = useState(false) // AI chat panel visibility

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

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    })
  }

  const handleGenerateReport = async (videoId) => {
    setGeneratingReport(true)
    try {
      const response = await apiPost(`/api/video/${videoId}/report`)

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
      const response = await apiDelete(`/api/video/${videoId}`)

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
    if (!token) return

    try {
      const response = await apiGet('/api/videos')
      const data = await response.json()
      setVideos(data.filter(v => v.status === 'completed'))
    } catch (error) {
      console.error('Failed to load videos:', error)
    }
  }

  const handleLoginSuccess = (userData, accessToken) => {
    setUser(userData)
    setToken(accessToken)
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setUser(null)
    setToken(null)
    setCurrentVideo(null)
    setVideos([])
  }

  useEffect(() => {
    // Check for existing auth
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      setToken(storedToken)
      setUser(JSON.parse(storedUser))

      // Refresh user data from server to get latest info (including team_name)
      refreshUserData(storedToken)
    }
  }, [])

  const refreshUserData = async (token) => {
    try {
      const response = await apiGet('/api/auth/me')
      if (response.ok) {
        const userData = await response.json()
        setUser(userData)
        localStorage.setItem('user', JSON.stringify(userData))
      }
    } catch (error) {
      console.error('Failed to refresh user data:', error)
    }
  }

  useEffect(() => {
    if (token) {
      loadVideos()
    }
  }, [token])

  // Show login if not authenticated
  if (!user || !token) {
    return <Login onLoginSuccess={handleLoginSuccess} />
  }

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
          <div className="header-user-info">
            {user.role === 'admin' && (
              <div className="view-toggle">
                <button
                  className={`toggle-btn ${currentView === 'videos' ? 'active' : ''}`}
                  onClick={() => setCurrentView('videos')}
                >
                  <VideoLibraryIcon sx={{ fontSize: '1rem' }} />
                  Videos
                </button>
                <button
                  className={`toggle-btn ${currentView === 'admin' ? 'active' : ''}`}
                  onClick={() => setCurrentView('admin')}
                >
                  <GroupsIcon sx={{ fontSize: '1rem' }} />
                  Teams
                </button>
              </div>
            )}
            <div className="user-details">
              <span className="user-name">{user.full_name}</span>
              <div className="user-badges">
                <span className="user-role">{user.role}</span>
                {user.team_name && (
                  <span className="user-team">
                    <GroupsIcon sx={{ fontSize: '0.875rem' }} />
                    {user.team_name}
                  </span>
                )}
              </div>
            </div>
            <button className="logout-btn" onClick={handleLogout}>
              <LogoutIcon sx={{ fontSize: '1.1rem' }} />
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="app-container">
        {currentView === 'admin' ? (
          <div className="main-content" style={{ maxWidth: '100%' }}>
            <AdminPanel user={user} />
          </div>
        ) : (
          <>
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
                <div className={`player-interface ${!showAIPanel ? 'ai-panel-closed' : ''}`}>
                  <div className="video-section">
                    <div className="video-header">
                      <div className="video-header-info">
                        <h3 className="video-header-title">
                          {currentVideo.name || currentVideo.filename}
                        </h3>
                      </div>
                    </div>
                    <VideoPlayer
                      videoId={currentVideo.video_id}
                      seekTime={videoTime}
                    />
                    <div className="video-actions">
                      {!showAIPanel && (
                        <button
                          className="ask-ai-btn"
                          onClick={() => setShowAIPanel(true)}
                        >
                          <SmartToyIcon sx={{ fontSize: '1.1rem' }} />
                          Ask AI
                        </button>
                      )}
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
                    <div className="video-details-section">
                      <h4 className="video-details-heading">Description</h4>
                      <p className="video-details-description">
                        {currentVideo.description || 'No description available'}
                      </p>
                      <div className="video-metadata">
                        {currentVideo.author_name && (
                          <div className="video-meta-item">
                            <PersonIcon sx={{ fontSize: '1rem' }} />
                            <span className="meta-label">Author:</span>
                            <span className="meta-value">{currentVideo.author_name}</span>
                          </div>
                        )}
                        <div className="video-meta-item">
                          <CalendarTodayIcon sx={{ fontSize: '1rem' }} />
                          <span className="meta-label">Uploaded:</span>
                          <span className="meta-value">{formatDate(currentVideo.upload_date)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {showAIPanel && (
                    <div className="chat-section">
                      <div className="ai-panel-header">
                        <h3>
                          <SmartToyIcon sx={{ fontSize: '1.1rem' }} />
                          AI Learning Assistant
                        </h3>
                        <button
                          className="close-ai-btn"
                          onClick={() => setShowAIPanel(false)}
                          title="Close AI Assistant"
                        >
                          <CloseIcon sx={{ fontSize: '1.2rem' }} />
                        </button>
                      </div>
                      <ChatInterface
                        videoId={currentVideo.video_id}
                        onTimestampClick={handleTimestampClick}
                        showHeader={false}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* <footer className="paytm-footer">
        <div className="footer-stripe"></div>
      </footer> */}
    </div>
  )
}

export default App
