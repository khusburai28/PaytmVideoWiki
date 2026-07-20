import { useState, useEffect } from 'react'
import VideoPlayer from './components/VideoPlayer'
import ChatInterface from './components/ChatInterface'
import UploadVideo from './components/UploadVideo'
import VideoSidebar from './components/VideoSidebar'
import Login from './components/Login'
import AdminPanel from './components/AdminPanel'
import ReportModal from './components/ReportModal'
import DiagramModal from './components/DiagramModal'
import DeleteIcon from '@mui/icons-material/Delete'
import DescriptionIcon from '@mui/icons-material/Description'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import LogoutIcon from '@mui/icons-material/Logout'
import GroupsIcon from '@mui/icons-material/Groups'
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary'
import PersonIcon from '@mui/icons-material/Person'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import CloseIcon from '@mui/icons-material/Close'
import { apiGet, apiPost, apiDelete } from './utils/api'
import './App.css'

const intelligenceModules = [
  {
    title: 'Universal Ingestion',
    description: 'Index field videos, procedures, inspection notes, OEM references, drawings, and audit evidence into one searchable asset memory.',
    metric: '7-12',
    label: 'systems unified'
  },
  {
    title: 'Asset Knowledge Graph',
    description: 'Connect equipment tags, people, dates, process parameters, incidents, work orders, and regulatory clauses across every record.',
    metric: '360',
    label: 'asset context'
  },
  {
    title: 'Maintenance & RCA',
    description: 'Surface prior failures, inspection trends, troubleshooting paths, and recommended next actions before downtime escalates.',
    metric: '18-22%',
    label: 'downtime risk'
  },
  {
    title: 'Compliance Intelligence',
    description: 'Map procedures and evidence to Factory Act, OISD, PESO, environmental, quality, and customer audit requirements.',
    metric: 'live',
    label: 'audit readiness'
  }
]

const industrialPrompts = [
  'Which assets have repeated seal failures and what evidence supports the pattern?',
  'Create an RCA brief for Pump P-204 using prior inspection and maintenance context.',
  'Show compliance gaps against PESO and OISD requirements for this operating area.',
  'What lessons learned should the shift team know before restarting the line?'
]

function App() {
  const [currentVideo, setCurrentVideo] = useState(null)
  const [videoTime, setVideoTime] = useState(0)
  const [videos, setVideos] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [currentView, setCurrentView] = useState('videos') // 'videos' or 'admin'
  const [showAIPanel, setShowAIPanel] = useState(false) // AI chat panel visibility
  const [showReportModal, setShowReportModal] = useState(false) // Report modal visibility
  const [showDiagramModal, setShowDiagramModal] = useState(false) // Diagram modal visibility
  const [generatingDiagram, setGeneratingDiagram] = useState(false)
  const [diagramData, setDiagramData] = useState(null)

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

  const handleGenerateReport = async (additionalInstructions) => {
    setGeneratingReport(true)
    try {
      const body = additionalInstructions
        ? { additional_instructions: additionalInstructions }
        : {}

      const response = await apiPost(
        `/api/video/${currentVideo.video_id}/report`,
        body
      )

      if (!response.ok) {
        throw new Error('Failed to generate report')
      }

      // Get the PDF blob
      const blob = await response.blob()

      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${currentVideo.name || 'asset-record'}_intelligence_report.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      setShowReportModal(false)
      alert('Report generated successfully!')
    } catch (error) {
      console.error('Failed to generate report:', error)
      alert('Failed to generate report. Please try again.')
    } finally {
      setGeneratingReport(false)
    }
  }

  const handleGenerateDiagram = async (query) => {
    setGeneratingDiagram(true)
    setDiagramData(null)
    try {
      const response = await apiPost(
        `/api/video/${currentVideo.video_id}/diagram`,
        { query }
      )

      if (!response.ok) {
        throw new Error('Failed to generate diagram')
      }

      const data = await response.json()
      setDiagramData(data.diagram)
    } catch (error) {
      console.error('Failed to generate diagram:', error)
      alert('Failed to generate diagram. Please try again.')
    } finally {
      setGeneratingDiagram(false)
    }
  }

  const handleDeleteVideo = async (videoId) => {
    if (!confirm('Are you sure you want to delete this knowledge record? This action cannot be undone.')) {
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

      alert('Knowledge record deleted successfully')
    } catch (error) {
      console.error('Failed to delete knowledge record:', error)
      alert('Failed to delete knowledge record. Please try again.')
    }
  }

  const loadVideos = async () => {
    if (!token) return

    try {
      const response = await apiGet('/api/videos')
      const data = await response.json()
      const records = Array.isArray(data) ? data : (data.videos || data.records || [])
      setVideos(records.filter(v => v.status === 'completed'))
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

  // Show team membership required message for non-admin users without a team
  if (user.role !== 'admin' && !user.team_id) {
    return (
      <div className="app">
        <header className="app-header">
          <div className="header-content">
            <div className="header-logo">
              <div>
                <h1>AssetOps Brain</h1>
                <p>Industrial knowledge intelligence for safer, faster operations</p>
              </div>
            </div>
            <div className="header-user-info">
              <div className="user-details">
                <span className="user-name">{user.full_name}</span>
                <div className="user-badges">
                  <span className="user-role">{user.role}</span>
                </div>
              </div>
              <button className="logout-btn" onClick={handleLogout}>
                <LogoutIcon sx={{ fontSize: '1.1rem' }} />
                Logout
              </button>
            </div>
          </div>
        </header>
        <div className="team-required-container">
          <div className="team-required-card">
            <GroupsIcon sx={{ fontSize: '4rem', color: '#2563EB', marginBottom: '1rem' }} />
            <h2>Team Membership Required</h2>
            <p>You must be part of a plant, project, or function team to access AssetOps Brain.</p>
            <p className="contact-message">
              Please contact your <strong>Team Lead</strong> or <strong>Admin</strong> to be added to a team.
            </p>
            <div className="user-info-box">
              <p><strong>Your Email:</strong> {user.email}</p>
              <p><strong>Your Name:</strong> {user.full_name}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-logo">
            {/* <img src="/logo.svg" alt="AssetOps Logo" className="paytm-logo-img" />
            <div style={{ borderLeft: '2px solid #E0E0E0', height: '30px', margin: '0 0.5rem' }}></div> */}
            <div>
              <h1>AssetOps Brain</h1>
              <p>Unified Asset & Operations Intelligence</p>
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
                  Asset Records
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
                  <section className="ops-hero">
                    <div className="ops-hero-copy">
                      <span className="ops-eyebrow">Industrial Intelligence / Knowledge Engineering</span>
                      <h2>Turn fragmented plant knowledge into one operational brain.</h2>
                      <p>
                        Ingest operational evidence, extract asset context, and let teams query maintenance,
                        safety, quality, and compliance knowledge at the point of need.
                      </p>
                    </div>
                    <div className="ops-signal-panel">
                      <div>
                        <span className="signal-value">35%</span>
                        <span className="signal-label">time lost searching for information</span>
                      </div>
                      <div>
                        <span className="signal-value">25%</span>
                        <span className="signal-label">experienced engineers retiring this decade</span>
                      </div>
                    </div>
                  </section>

                  <section className="module-grid">
                    {intelligenceModules.map((module) => (
                      <article className="module-card" key={module.title}>
                        <div className="module-stat">
                          <span>{module.metric}</span>
                          <small>{module.label}</small>
                        </div>
                        <h3>{module.title}</h3>
                        <p>{module.description}</p>
                      </article>
                    ))}
                  </section>

                  <UploadVideo onVideoUploaded={handleVideoUploaded} />

                  <section className="prompt-bank">
                    <h3>Copilot queries your demo can answer</h3>
                    <div className="prompt-grid">
                      {industrialPrompts.map((prompt) => (
                        <div className="prompt-chip" key={prompt}>{prompt}</div>
                      ))}
                    </div>
                  </section>
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
                          Ask Copilot
                        </button>
                      )}
                      <button
                        className="generate-diagram-btn"
                        onClick={() => setShowDiagramModal(true)}
                        disabled={generatingDiagram}
                      >
                        <AccountTreeIcon sx={{ fontSize: '1.1rem' }} />
                        Knowledge Graph
                      </button>
                      <button
                        className="generate-report-btn"
                        onClick={() => setShowReportModal(true)}
                        disabled={generatingReport}
                      >
                        <DescriptionIcon sx={{ fontSize: '1.1rem' }} />
                        Evidence Pack
                      </button>
                      <button
                        className="delete-video-btn"
                        onClick={() => handleDeleteVideo(currentVideo.video_id)}
                        disabled={generatingReport}
                      >
                        <DeleteIcon sx={{ fontSize: '1.1rem' }} />
                        Delete Record
                      </button>
                    </div>
                    <div className="video-details-section">
                      <h4 className="video-details-heading">Operational Context</h4>
                      <p className="video-details-description">
                        {currentVideo.description || 'No description available'}
                      </p>
                      <div className="video-metadata">
                        {currentVideo.author_name && (
                          <div className="video-meta-item">
                            <PersonIcon sx={{ fontSize: '1rem' }} />
                            <span className="meta-label">Owner:</span>
                            <span className="meta-value">{currentVideo.author_name}</span>
                          </div>
                        )}
                        <div className="video-meta-item">
                          <CalendarTodayIcon sx={{ fontSize: '1rem' }} />
                          <span className="meta-label">Indexed:</span>
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
                          Industrial Knowledge Copilot
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

      {/* Report Generation Modal */}
      {currentVideo && (
        <ReportModal
          isOpen={showReportModal}
          onClose={() => setShowReportModal(false)}
          onGenerate={handleGenerateReport}
          videoName={currentVideo.name || currentVideo.filename}
          isGenerating={generatingReport}
        />
      )}

      {/* Diagram Generation Modal */}
      {currentVideo && (
        <DiagramModal
          isOpen={showDiagramModal}
          onClose={() => {
            setShowDiagramModal(false)
            setDiagramData(null)
          }}
          onGenerate={handleGenerateDiagram}
          videoName={currentVideo.name || currentVideo.filename}
          isGenerating={generatingDiagram}
          diagramData={diagramData}
        />
      )}
    </div>
  )
}

export default App
