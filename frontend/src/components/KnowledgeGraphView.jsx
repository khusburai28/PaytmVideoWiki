import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import CloseIcon from '@mui/icons-material/Close'
import DescriptionIcon from '@mui/icons-material/Description'
import { apiGet } from '../utils/api'
import './KnowledgeGraphView.css'

const TYPE_COLORS = {
  equipment: '#2DD4BF',
  personnel: '#38BDF8',
  date: '#94A3B8',
  regulation: '#F87171',
  process_parameter: '#4ADE80',
  location: '#C084FC',
  organization: '#F472B6',
  incident: '#DC2626',
  work_order: '#A3E635',
}

const TYPE_LABELS = {
  equipment: 'Equipment',
  personnel: 'Personnel',
  date: 'Date',
  regulation: 'Regulation',
  process_parameter: 'Process Parameter',
  location: 'Location',
  organization: 'Organization',
  incident: 'Incident',
  work_order: 'Work Order',
}

function KnowledgeGraphView({ documentId, onOpenDocument }) {
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedEntity, setSelectedEntity] = useState(null)
  const [entityDetail, setEntityDetail] = useState(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      setDimensions({ width: Math.max(width, 300), height: Math.max(height, 400) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const url = documentId ? `/api/graph/document/${documentId}` : '/api/graph'

    apiGet(url)
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load knowledge graph')
        const data = await res.json()
        if (cancelled) return
        setGraphData(data)
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))

    return () => { cancelled = true }
  }, [documentId])

  const forceGraphData = useMemo(() => ({
    nodes: graphData.nodes.map((n) => ({ ...n })),
    links: graphData.edges.map((e) => ({ ...e })),
  }), [graphData])

  const handleNodeClick = useCallback((node) => {
    setSelectedEntity(node.id)
    setEntityDetail(null)
    apiGet(`/api/graph/entity/${encodeURIComponent(node.id)}`)
      .then(async (res) => {
        if (!res.ok) return
        const data = await res.json()
        setEntityDetail(data)
      })
      .catch(() => {})
  }, [])

  const typeCounts = useMemo(() => {
    const counts = {}
    for (const n of graphData.nodes) {
      counts[n.type] = (counts[n.type] || 0) + 1
    }
    return counts
  }, [graphData.nodes])

  return (
    <div className="knowledge-graph-view">
      <div className="graph-header">
        <h2>
          <AccountTreeIcon sx={{ fontSize: '1.2rem', verticalAlign: 'middle', marginRight: '0.5rem' }} />
          {documentId ? 'Extracted Entities for This Record' : 'Unified Asset Knowledge Graph'}
        </h2>
        <p>
          {graphData.nodes.length} entities · {graphData.edges.length} relationships extracted across your knowledge base
        </p>
      </div>

      <div className="graph-body">
        <div className="graph-canvas-wrap" ref={containerRef}>
          {loading && <div className="graph-status">Loading knowledge graph...</div>}
          {!loading && error && <div className="graph-status">{error}</div>}
          {!loading && !error && graphData.nodes.length === 0 && (
            <div className="graph-status">
              No entities extracted yet. Ingest a document to start building the graph.
            </div>
          )}
          {!loading && !error && graphData.nodes.length > 0 && (
            <ForceGraph2D
              graphData={forceGraphData}
              width={dimensions.width}
              height={dimensions.height}
              backgroundColor="#080B0F"
              nodeId="id"
              nodeLabel={(n) => `${TYPE_LABELS[n.type] || n.type}: ${n.label}`}
              nodeColor={(n) => TYPE_COLORS[n.type] || '#94A3B8'}
              nodeRelSize={5}
              nodeVal={(n) => 1 + Math.min(n.mention_count || 1, 8)}
              linkLabel={(l) => l.relation}
              linkColor={() => 'rgba(148, 163, 184, 0.4)'}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              onNodeClick={handleNodeClick}
              cooldownTicks={80}
            />
          )}
        </div>

        {Object.keys(typeCounts).length > 0 && (
          <div className="graph-legend">
            {Object.entries(typeCounts).map(([type, count]) => (
              <div key={type} className="legend-item">
                <span className="legend-dot" style={{ background: TYPE_COLORS[type] || '#94A3B8' }} />
                <span className="legend-label">{TYPE_LABELS[type] || type}</span>
                <span className="legend-count">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedEntity && (
        <div className="entity-panel">
          <div className="entity-panel-header">
            <h3>{entityDetail?.node?.label || selectedEntity}</h3>
            <button className="entity-panel-close" onClick={() => setSelectedEntity(null)}>
              <CloseIcon sx={{ fontSize: '1.1rem' }} />
            </button>
          </div>
          {!entityDetail ? (
            <p className="entity-panel-loading">Loading...</p>
          ) : (
            <>
              <span
                className="entity-type-badge"
                style={{ background: TYPE_COLORS[entityDetail.node.type] || '#94A3B8' }}
              >
                {TYPE_LABELS[entityDetail.node.type] || entityDetail.node.type}
              </span>
              <p className="entity-mentions">Mentioned {entityDetail.node.mention_count} time(s)</p>

              {entityDetail.documents.length > 0 && (
                <div className="entity-section">
                  <h4>Found in</h4>
                  {entityDetail.documents.map((doc) => (
                    <button
                      key={doc.document_id}
                      className="entity-document-chip"
                      onClick={() => onOpenDocument && onOpenDocument(doc.document_id)}
                    >
                      <DescriptionIcon sx={{ fontSize: '0.95rem' }} />
                      {doc.document_name}
                    </button>
                  ))}
                </div>
              )}

              {entityDetail.neighbors.length > 0 && (
                <div className="entity-section">
                  <h4>Related entities</h4>
                  {entityDetail.neighbors.map((n) => (
                    <div key={n.id} className="entity-neighbor-row">
                      <span className="legend-dot" style={{ background: TYPE_COLORS[n.type] || '#94A3B8' }} />
                      {n.label}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default KnowledgeGraphView
