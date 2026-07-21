import { useState } from 'react'
import ZoomInIcon from '@mui/icons-material/ZoomIn'
import ZoomOutIcon from '@mui/icons-material/ZoomOut'
import './ImageViewer.css'

function ImageViewer({ documentId }) {
  const [zoomed, setZoomed] = useState(false)
  const token = localStorage.getItem('access_token')
  const src = `/api/document/${documentId}/file?token=${encodeURIComponent(token)}`

  return (
    <div className="image-viewer-container">
      <div className={`image-viewer-frame ${zoomed ? 'zoomed' : ''}`} onClick={() => setZoomed(!zoomed)}>
        <img src={src} alt="Document" />
      </div>
      <button className="image-zoom-btn" onClick={() => setZoomed(!zoomed)}>
        {zoomed ? <ZoomOutIcon sx={{ fontSize: '1rem' }} /> : <ZoomInIcon sx={{ fontSize: '1rem' }} />}
        {zoomed ? 'Zoom out' : 'Zoom in'}
      </button>
    </div>
  )
}

export default ImageViewer
