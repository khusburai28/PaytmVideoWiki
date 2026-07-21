import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import WavingHandIcon from '@mui/icons-material/WavingHand'
import SendIcon from '@mui/icons-material/Send'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import CloseIcon from '@mui/icons-material/Close'
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'
import ImageIcon from '@mui/icons-material/Image'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import TableChartIcon from '@mui/icons-material/TableChart'
import OndemandVideoIcon from '@mui/icons-material/OndemandVideo'
import { apiPost } from '../utils/api'
import './ChatInterface.css'

const SOURCE_ICONS = {
  video: OndemandVideoIcon,
  pdf: PictureAsPdfIcon,
  image: ImageIcon,
  spreadsheet: TableChartIcon,
}

function ChatInterface({ documentId, onSourceClick, showHeader = true }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState([])
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Reset the conversation when switching between document-scoped and corpus-wide chat
  useEffect(() => {
    setMessages([])
  }, [documentId])

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files)
    setAttachedFiles(prev => [...prev, ...files])
  }

  const removeFile = (index) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index))
  }

  const getFileIcon = (file) => {
    if (file.type.startsWith('image/')) {
      return <ImageIcon sx={{ fontSize: '1.2rem' }} />
    } else if (file.type === 'application/pdf') {
      return <PictureAsPdfIcon sx={{ fontSize: '1.2rem' }} />
    } else {
      return <InsertDriveFileIcon sx={{ fontSize: '1.2rem' }} />
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const handleSend = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || loading) return

    const userMessage = {
      role: 'user',
      content: input,
      files: attachedFiles.map(f => ({ name: f.name, size: f.size, type: f.type })),
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    const currentInput = input
    const currentFiles = attachedFiles
    setInput('')
    setAttachedFiles([])
    setLoading(true)

    try {
      const formData = new FormData()
      if (documentId) {
        formData.append('document_id', documentId)
      }
      formData.append('message', currentInput)
      formData.append('conversation_history', JSON.stringify(messages))

      currentFiles.forEach((file) => {
        formData.append('files', file)
      })

      const response = await apiPost('/api/chat', formData)

      if (!response.ok) {
        throw new Error('Failed to get response')
      }

      const data = await response.json()

      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString(),
        sources: data.sources || []
      }

      setMessages(prev => [...prev, assistantMessage])

    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
        isError: true
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-interface">
      {showHeader && (
        <div className="chat-header">
          <h2>
            <SmartToyIcon sx={{ fontSize: '1.2rem', verticalAlign: 'middle', marginRight: '0.5rem' }} />
            Industrial Knowledge Copilot
          </h2>
          <p>
            {documentId
              ? 'Ask across this record\'s indexed content'
              : 'Ask across your entire team\'s knowledge base'}
          </p>
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <p>
              <WavingHandIcon sx={{ fontSize: '1.1rem', verticalAlign: 'middle', marginRight: '0.3rem' }} />
              Welcome to your Industrial Knowledge Copilot.
            </p>
            <p>Ask about asset behavior, failure patterns, safety procedures, compliance evidence, or lessons learned. I will answer with cited sources from the indexed knowledge base.</p>
            <div className="example-questions">
              <p><strong>Example questions:</strong></p>
              <ul>
                <li>"Which asset tags and process parameters are mentioned?"</li>
                <li>"Summarize possible failure modes and recommended checks."</li>
                <li>"What compliance or safety evidence can I cite for an audit?"</li>
                <li>"Create a shift handover brief with risks and next actions."</li>
              </ul>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">
              <div className="message-text">
                {message.role === 'assistant' ? (
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                ) : (
                  <>
                    {message.content}
                    {message.files && message.files.length > 0 && (
                      <div className="message-files">
                        {message.files.map((file, idx) => (
                          <div key={idx} className="message-file-item">
                            {getFileIcon(file)}
                            <span className="file-name">{file.name}</span>
                            <span className="file-size">({formatFileSize(file.size)})</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                <div className="sources-section">
                  <p className="sources-label">Sources</p>
                  {message.sources.map((source, idx) => {
                    const SourceIcon = SOURCE_ICONS[source.document_type] || InsertDriveFileIcon
                    return (
                      <div
                        key={idx}
                        className="source-chip"
                        onClick={() => onSourceClick && onSourceClick(source)}
                        title={`Open ${source.document_name}`}
                      >
                        <SourceIcon sx={{ fontSize: '1.1rem' }} className="source-chip-icon" />
                        <div className="source-chip-text">
                          <span className="source-chip-name">{source.document_name}</span>
                          <span className="source-chip-locator">{source.locator}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message assistant loading">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-wrapper">
        {attachedFiles.length > 0 && (
          <div className="attached-files-preview">
            {attachedFiles.map((file, index) => (
              <div key={index} className="attached-file-chip">
                {getFileIcon(file)}
                <span className="attached-file-name">{file.name}</span>
                <span className="attached-file-size">{formatFileSize(file.size)}</span>
                <button
                  className="remove-file-btn"
                  onClick={() => removeFile(index)}
                  title="Remove file"
                >
                  <CloseIcon sx={{ fontSize: '1rem' }} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="chat-input-container">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.pdf,.doc,.docx,.txt"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          <button
            className="attach-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            title="Attach file"
          >
            <AttachFileIcon sx={{ fontSize: '1.2rem' }} />
          </button>
          <textarea
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question..."
            rows={1}
            disabled={loading}
          />
          <button
            className="send-button"
            onClick={handleSend}
            disabled={(!input.trim() && attachedFiles.length === 0) || loading}
          >
            {loading ? '...' : <SendIcon sx={{ fontSize: '1.2rem' }} />}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatInterface
