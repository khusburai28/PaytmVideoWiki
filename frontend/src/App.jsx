import { useState, useEffect } from 'react'
import VideoPlayer from './components/VideoPlayer'
import PdfViewer from './components/viewers/PdfViewer'
import ImageViewer from './components/viewers/ImageViewer'
import SpreadsheetViewer from './components/viewers/SpreadsheetViewer'
import ChatInterface from './components/ChatInterface'
import UploadDocument from './components/UploadDocument'
import DocumentSidebar from './components/DocumentSidebar'
import KnowledgeGraphView from './components/KnowledgeGraphView'
import Login from './components/Login'
import AdminPanel from './components/AdminPanel'
import ReportModal from './components/ReportModal'
import DiagramModal from './components/DiagramModal'
import DeleteIcon from '@mui/icons-material/Delete'
import DescriptionIcon from '@mui/icons-material/Description'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import HubIcon from '@mui/icons-material/Hub'
import LogoutIcon from '@mui/icons-material/Logout'
import GroupsIcon from '@mui/icons-material/Groups'
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks'
import ChatIcon from '@mui/icons-material/Chat'
import PersonIcon from '@mui/icons-material/Person'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import CloseIcon from '@mui/icons-material/Close'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import TableChartIcon from '@mui/icons-material/TableChart'
import OndemandVideoIcon from '@mui/icons-material/OndemandVideo'
import { apiGet, apiPost, apiDelete } from './utils/api'
import './App.css'

const checklistItems = [
  'Every format lands in one searchable memory',
  'Citations down to the page, row, or timestamp',
  'Equipment tags link automatically across records'
]

const industrialPrompts = [
  'Create an RCA brief for Pump P-204 from prior inspections',
  'What compliance gaps exist against PESO and OISD?'
]

function App() {
  const [currentDocument, setCurrentDocument] = useState(null)
  const [documentTime, setDocumentTime] = useState(0)
  const [viewerTarget, setViewerTarget] = useState(null)
  const [documents, setDocuments] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [currentView, setCurrentView] = useState('documents') // 'documents' | 'copilot' | 'graph' | 'admin'
  const [showAIPanel, setShowAIPanel] = useState(false)
  const [showReportModal, setShowReportModal] = useState(false)
  const [showDiagramModal, setShowDiagramModal] = useState(false)
  const [generatingDiagram, setGeneratingDiagram] = useState(false)
  const [diagramData, setDiagramData] = useState(null)

  const handleDocumentUploaded = (docInfo) => {
    setCurrentDocument(docInfo)
    loadDocuments()
  }

  const handleSourceClick = (source) => {
    const target = documents.find(d => d.document_id === source.document_id)
    if (target) {
      setCurrentDocument(target)
      setCurrentView('documents')
    }

    if (source.document_type === 'video' && source.start_time != null) {
      setDocumentTime(source.start_time)
      setViewerTarget(null)
    } else if (source.document_type === 'pdf' && source.page_number != null) {
      setViewerTarget({ page: source.page_number })
    } else {
      setViewerTarget(null)
    }
  }

  const handleDocumentSelect = (doc) => {
    setCurrentDocument(doc)
    setViewerTarget(null)
    setCurrentView('documents')
  }

  const handleOpenDocumentFromGraph = (documentId) => {
    const target = documents.find(d => d.document_id === documentId)
    if (target) {
      setCurrentDocument(target)
      setViewerTarget(null)
      setCurrentView('documents')
    }
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
        `/api/document/${currentDocument.document_id}/report`,
        body
      )

      if (!response.ok) {
        throw new Error('Failed to generate report')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${currentDocument.name || 'asset-record'}_intelligence_report.pdf`
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
        `/api/document/${currentDocument.document_id}/diagram`,
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

  const handleDeleteDocument = async (documentId) => {
    if (!confirm('Are you sure you want to delete this knowledge record? This action cannot be undone.')) {
      return
    }

    try {
      const response = await apiDelete(`/api/document/${documentId}`)

      if (!response.ok) {
        throw new Error('Failed to delete document')
      }

      if (currentDocument?.document_id === documentId) {
        setCurrentDocument(null)
      }

      loadDocuments()

      alert('Knowledge record deleted successfully')
    } catch (error) {
      console.error('Failed to delete knowledge record:', error)
      alert('Failed to delete knowledge record. Please try again.')
    }
  }

  const loadDocuments = async () => {
    if (!token) return

    try {
      const response = await apiGet('/api/documents')
      const data = await response.json()
      const records = Array.isArray(data) ? data : (data.documents || data.records || [])
      setDocuments(records.filter(d => d.status === 'completed'))
    } catch (error) {
      console.error('Failed to load documents:', error)
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
    setCurrentDocument(null)
    setDocuments([])
  }

  useEffect(() => {
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      setToken(storedToken)
      setUser(JSON.parse(storedUser))
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
      loadDocuments()
    }
  }, [token])

  if (!user || !token) {
    return <Login onLoginSuccess={handleLoginSuccess} />
  }

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

  const renderViewer = () => {
    if (!currentDocument) return null
    switch (currentDocument.document_type) {
      case 'pdf':
        return <PdfViewer documentId={currentDocument.document_id} seekTarget={viewerTarget} />
      case 'image':
        return <ImageViewer documentId={currentDocument.document_id} />
      case 'spreadsheet':
        return <SpreadsheetViewer documentId={currentDocument.document_id} />
      case 'video':
      default:
        return <VideoPlayer videoId={currentDocument.document_id} seekTime={documentTime} />
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-logo">
            <div>
              <h1>AssetOps Brain</h1>
              <p>Unified Asset & Operations Intelligence</p>
            </div>
          </div>
          <div className="header-user-info">
            <div className="view-toggle">
              <button
                className={`toggle-btn ${currentView === 'documents' ? 'active' : ''}`}
                onClick={() => setCurrentView('documents')}
              >
                <LibraryBooksIcon sx={{ fontSize: '1rem' }} />
                Records
              </button>
              <button
                className={`toggle-btn ${currentView === 'copilot' ? 'active' : ''}`}
                onClick={() => setCurrentView('copilot')}
              >
                <ChatIcon sx={{ fontSize: '1rem' }} />
                Copilot
              </button>
              <button
                className={`toggle-btn ${currentView === 'graph' ? 'active' : ''}`}
                onClick={() => setCurrentView('graph')}
              >
                <HubIcon sx={{ fontSize: '1rem' }} />
                Knowledge Graph
              </button>
              {user.role === 'admin' && (
                <button
                  className={`toggle-btn ${currentView === 'admin' ? 'active' : ''}`}
                  onClick={() => setCurrentView('admin')}
                >
                  <GroupsIcon sx={{ fontSize: '1rem' }} />
                  Teams
                </button>
              )}
            </div>
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
        ) : currentView === 'graph' ? (
          <div className="main-content graph-view-page">
            <KnowledgeGraphView onOpenDocument={handleOpenDocumentFromGraph} />
          </div>
        ) : currentView === 'copilot' ? (
          <div className="main-content copilot-page">
            <ChatInterface documentId={null} onSourceClick={handleSourceClick} />
          </div>
        ) : (
          <>
            <DocumentSidebar
              documents={documents}
              currentDocument={currentDocument}
              onDocumentSelect={handleDocumentSelect}
            />

            <div className="main-content">
              {!currentDocument ? (
                <div className="upload-section">
                  <section className="ops-hero">
                    <div className="ops-hero-copy">
                      <span className="ops-eyebrow-pill">
                        <span className="pill-dot" />
                        4 formats · 1 knowledge graph
                      </span>
                      <h2>One operational brain<br />for every asset record.</h2>
                      <p>Feed it videos, PDFs, photos, and spreadsheets. Ask it anything. It cites its sources.</p>
                      <div className="ops-hero-actions">
                        <button
                          className="btn-pill btn-pill-light"
                          onClick={() => document.getElementById('ingest-panel')?.scrollIntoView({ behavior: 'smooth' })}
                        >
                          Start Ingesting
                        </button>
                        <button className="btn-pill btn-pill-accent" onClick={() => setCurrentView('graph')}>
                          See the Graph <HubIcon sx={{ fontSize: '1.05rem' }} />
                        </button>
                      </div>
                      <ul className="ops-checklist">
                        {checklistItems.map((item) => (
                          <li key={item}>
                            <CheckCircleIcon />
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="ops-constellation" aria-hidden="true">
                      <svg className="constellation-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
                        <path d="M 14 12 Q 40 30, 50 50" />
                        <path d="M 10 66 Q 30 55, 50 50" />
                        <path d="M 78 32 Q 60 42, 50 50" />
                        <path d="M 82 80 Q 65 65, 50 50" />
                      </svg>
                      <div className="constellation-node" />
                      <div className="evidence-card evidence-card-1">
                        <PictureAsPdfIcon />
                        Page 4 · Inspection Report
                      </div>
                      <div className="evidence-card evidence-card-2">
                        <TableChartIcon />
                        WO-2041 · B-102
                      </div>
                      <div className="evidence-card evidence-card-3 tag-chip">P-204</div>
                      <div className="evidence-card evidence-card-4">
                        <OndemandVideoIcon />
                        12:34 · Shift Briefing
                      </div>
                    </div>
                  </section>

                  <div id="ingest-panel">
                    <UploadDocument onDocumentUploaded={handleDocumentUploaded} />
                  </div>

                  <section className="prompt-bank">
                    <h3>Try asking the copilot</h3>
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
                          {currentDocument.name || currentDocument.filename}
                        </h3>
                      </div>
                    </div>
                    {renderViewer()}
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
                        Flow Diagram
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
                        onClick={() => handleDeleteDocument(currentDocument.document_id)}
                        disabled={generatingReport}
                      >
                        <DeleteIcon sx={{ fontSize: '1.1rem' }} />
                        Delete Record
                      </button>
                    </div>
                    <div className="video-details-section">
                      <h4 className="video-details-heading">Operational Context</h4>
                      <p className="video-details-description">
                        {currentDocument.description || 'No description available'}
                      </p>
                      <div className="video-metadata">
                        {currentDocument.author_name && (
                          <div className="video-meta-item">
                            <PersonIcon sx={{ fontSize: '1rem' }} />
                            <span className="meta-label">Owner:</span>
                            <span className="meta-value">{currentDocument.author_name}</span>
                          </div>
                        )}
                        <div className="video-meta-item">
                          <CalendarTodayIcon sx={{ fontSize: '1rem' }} />
                          <span className="meta-label">Indexed:</span>
                          <span className="meta-value">{formatDate(currentDocument.upload_date)}</span>
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
                        documentId={currentDocument.document_id}
                        onSourceClick={handleSourceClick}
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

      {currentDocument && (
        <ReportModal
          isOpen={showReportModal}
          onClose={() => setShowReportModal(false)}
          onGenerate={handleGenerateReport}
          documentName={currentDocument.name || currentDocument.filename}
          isGenerating={generatingReport}
        />
      )}

      {currentDocument && (
        <DiagramModal
          isOpen={showDiagramModal}
          onClose={() => {
            setShowDiagramModal(false)
            setDiagramData(null)
          }}
          onGenerate={handleGenerateDiagram}
          documentName={currentDocument.name || currentDocument.filename}
          isGenerating={generatingDiagram}
          diagramData={diagramData}
        />
      )}
    </div>
  )
}

export default App
