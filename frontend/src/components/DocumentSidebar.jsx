import { useState, useMemo } from 'react'
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks'
import OndemandVideoIcon from '@mui/icons-material/OndemandVideo'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import ImageIcon from '@mui/icons-material/Image'
import TableChartIcon from '@mui/icons-material/TableChart'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import BarChartIcon from '@mui/icons-material/BarChart'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'
import PersonIcon from '@mui/icons-material/Person'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import SearchIcon from '@mui/icons-material/Search'
import './DocumentSidebar.css'

const TYPE_ICONS = {
  video: OndemandVideoIcon,
  pdf: PictureAsPdfIcon,
  image: ImageIcon,
  spreadsheet: TableChartIcon,
}

const TYPE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'video', label: 'Video' },
  { value: 'pdf', label: 'PDF' },
  { value: 'image', label: 'Image' },
  { value: 'spreadsheet', label: 'Sheet' },
]

function DocumentSidebar({ documents, currentDocument, onDocumentSelect }) {
  const [expandedDocument, setExpandedDocument] = useState(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const toggleExpand = (documentId) => {
    setExpandedDocument(expandedDocument === documentId ? null : documentId)
  }

  const formatDuration = (seconds) => {
    if (!seconds) return null
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')} min`
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
  }

  const filteredDocuments = useMemo(() => {
    const q = search.trim().toLowerCase()
    return documents.filter((doc) => {
      if (typeFilter !== 'all' && doc.document_type !== typeFilter) return false
      if (!q) return true
      const haystack = `${doc.name || ''} ${doc.filename || ''} ${doc.description || ''}`.toLowerCase()
      return haystack.includes(q)
    })
  }, [documents, search, typeFilter])

  return (
    <div className="document-sidebar">
      <div className="sidebar-header">
        <h2>
          <LibraryBooksIcon sx={{ fontSize: '1.3rem', verticalAlign: 'middle', marginRight: '0.5rem' }} />
          Asset Records
        </h2>
        <div className="sidebar-search">
          <SearchIcon sx={{ fontSize: '1rem' }} className="sidebar-search-icon" />
          <input
            type="text"
            placeholder="Search records..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="sidebar-type-filters">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.value}
              className={`type-filter-chip ${typeFilter === f.value ? 'active' : ''}`}
              onClick={() => setTypeFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-documents">
        {documents.length === 0 ? (
          <div className="sidebar-empty">
            <p>No records indexed yet</p>
            <p className="sidebar-empty-hint">Ingest your first operational evidence file to get started</p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="sidebar-empty">
            <p>No matching records</p>
            <p className="sidebar-empty-hint">Try a different search or filter</p>
          </div>
        ) : (
          filteredDocuments.map(doc => {
            const TypeIcon = TYPE_ICONS[doc.document_type] || OndemandVideoIcon
            const duration = formatDuration(doc.duration)
            return (
              <div
                key={doc.document_id}
                className={`sidebar-document-item ${currentDocument?.document_id === doc.document_id ? 'active' : ''}`}
              >
                <div
                  className="sidebar-document-header"
                  onClick={() => onDocumentSelect(doc)}
                >
                  <div className={`sidebar-document-icon type-${doc.document_type}`}>
                    <TypeIcon sx={{ fontSize: '1.3rem' }} />
                  </div>
                  <div className="sidebar-document-title-container">
                    <h3 className="sidebar-document-title">{doc.name || doc.filename}</h3>
                  </div>
                  <button
                    className="sidebar-expand-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleExpand(doc.document_id)
                    }}
                  >
                    {expandedDocument === doc.document_id ? (
                      <ExpandMoreIcon sx={{ fontSize: '1rem' }} />
                    ) : (
                      <ChevronRightIcon sx={{ fontSize: '1rem' }} />
                    )}
                  </button>
                </div>

                {expandedDocument === doc.document_id && (
                  <div className="sidebar-document-details">
                    <p className="sidebar-document-description">
                      {doc.description || 'No operational context'}
                    </p>
                    <div className="sidebar-document-meta">
                      {doc.author_name && (
                        <div className="sidebar-meta-item">
                          <span className="meta-icon">
                            <PersonIcon sx={{ fontSize: '0.9rem' }} />
                          </span>
                          <span>{doc.author_name}</span>
                        </div>
                      )}
                      {duration && (
                        <div className="sidebar-meta-item">
                          <span className="meta-icon">
                            <AccessTimeIcon sx={{ fontSize: '0.9rem' }} />
                          </span>
                          <span>{duration}</span>
                        </div>
                      )}
                      <div className="sidebar-meta-item">
                        <span className="meta-icon">
                          <BarChartIcon sx={{ fontSize: '0.9rem' }} />
                        </span>
                        <span>{doc.total_segments} evidence chunks</span>
                      </div>
                      <div className="sidebar-meta-item">
                        <span className="meta-icon">
                          <CalendarTodayIcon sx={{ fontSize: '0.9rem' }} />
                        </span>
                        <span>{formatDate(doc.upload_date)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default DocumentSidebar
