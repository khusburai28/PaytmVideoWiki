import './PdfViewer.css'

function PdfViewer({ documentId, seekTarget }) {
  const token = localStorage.getItem('access_token')
  const page = seekTarget?.page
  const src = `/api/document/${documentId}/file?token=${encodeURIComponent(token)}${page ? `#page=${page}` : ''}`

  return (
    <div className="pdf-viewer-container">
      {/* Native browser PDF rendering - no extra dependency, supports #page= deep links */}
      <iframe key={`${documentId}-${page || 0}`} className="pdf-viewer-frame" src={src} title="PDF document" />
    </div>
  )
}

export default PdfViewer
