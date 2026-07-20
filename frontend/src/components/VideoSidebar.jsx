import { useState } from 'react'
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary'
import OndemandVideoIcon from '@mui/icons-material/OndemandVideo'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import BarChartIcon from '@mui/icons-material/BarChart'
import CalendarTodayIcon from '@mui/icons-material/CalendarToday'
import PersonIcon from '@mui/icons-material/Person'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import './VideoSidebar.css'

function VideoSidebar({ videos, currentVideo, onVideoSelect }) {
  const [expandedVideo, setExpandedVideo] = useState(null)

  const toggleExpand = (videoId) => {
    setExpandedVideo(expandedVideo === videoId ? null : videoId)
  }

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A'
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

  return (
    <div className="video-sidebar">
      <div className="sidebar-header">
        <h2>
          <VideoLibraryIcon sx={{ fontSize: '1.3rem', verticalAlign: 'middle', marginRight: '0.5rem' }} />
          Asset Records
        </h2>
      </div>

      <div className="sidebar-videos">
        {videos.length === 0 ? (
          <div className="sidebar-empty">
            <p>No records indexed yet</p>
            <p className="sidebar-empty-hint">Ingest your first operational evidence file to get started</p>
          </div>
        ) : (
          videos.map(video => (
            <div
              key={video.video_id}
              className={`sidebar-video-item ${currentVideo?.video_id === video.video_id ? 'active' : ''}`}
            >
              <div
                className="sidebar-video-header"
                onClick={() => onVideoSelect(video)}
              >
                <div className="sidebar-video-icon">
                  <OndemandVideoIcon sx={{ fontSize: '1.5rem' }} />
                </div>
                <div className="sidebar-video-title-container">
                  <h3 className="sidebar-video-title">{video.name || video.filename}</h3>
                </div>
                <button
                  className="sidebar-expand-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    toggleExpand(video.video_id)
                  }}
                >
                  {expandedVideo === video.video_id ? (
                    <ExpandMoreIcon sx={{ fontSize: '1rem' }} />
                  ) : (
                    <ChevronRightIcon sx={{ fontSize: '1rem' }} />
                  )}
                </button>
              </div>

              {expandedVideo === video.video_id && (
                <div className="sidebar-video-details">
                  <p className="sidebar-video-description">
                    {video.description || 'No operational context'}
                  </p>
                  <div className="sidebar-video-meta">
                    {video.author_name && (
                      <div className="sidebar-meta-item">
                        <span className="meta-icon">
                          <PersonIcon sx={{ fontSize: '0.9rem' }} />
                        </span>
                        <span>{video.author_name}</span>
                      </div>
                    )}
                    <div className="sidebar-meta-item">
                      <span className="meta-icon">
                        <AccessTimeIcon sx={{ fontSize: '0.9rem' }} />
                      </span>
                      <span>{formatDuration(video.duration)}</span>
                    </div>
                    <div className="sidebar-meta-item">
                      <span className="meta-icon">
                        <BarChartIcon sx={{ fontSize: '0.9rem' }} />
                      </span>
                      <span>{video.total_segments} evidence segments</span>
                    </div>
                    <div className="sidebar-meta-item">
                      <span className="meta-icon">
                        <CalendarTodayIcon sx={{ fontSize: '0.9rem' }} />
                      </span>
                      <span>{formatDate(video.upload_date)}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default VideoSidebar
