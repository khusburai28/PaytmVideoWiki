import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import WavingHandIcon from '@mui/icons-material/WavingHand'
import LocationOnIcon from '@mui/icons-material/LocationOn'
import MovieIcon from '@mui/icons-material/Movie'
import SendIcon from '@mui/icons-material/Send'
import './ChatInterface.css'

function ChatInterface({ videoId, onTimestampClick }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const formatTime = (seconds) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }

  const parseTimeToSeconds = (timeStr) => {
    // Parse formats like "01:26" or "1:26:30"
    const parts = timeStr.split(':').map(Number)
    if (parts.length === 2) {
      // MM:SS
      return parts[0] * 60 + parts[1]
    } else if (parts.length === 3) {
      // HH:MM:SS
      return parts[0] * 3600 + parts[1] * 60 + parts[2]
    }
    return 0
  }

  const renderMessageWithClickableTimestamps = (text) => {
    // Replace [MM:SS] or [HH:MM:SS] patterns with clickable timestamps
    const timestampRegex = /\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g
    const parts = []
    let lastIndex = 0
    let match

    while ((match = timestampRegex.exec(text)) !== null) {
      // Add text before the timestamp
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index))
      }

      // Add clickable timestamp
      const timeStr = match[1]
      const seconds = parseTimeToSeconds(timeStr)
      parts.push(
        <span
          key={`ts-${match.index}`}
          className="inline-timestamp"
          onClick={() => onTimestampClick(seconds)}
          title={`Jump to ${timeStr}`}
        >
          [{timeStr}]
        </span>
      )

      lastIndex = match.index + match[0].length
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex))
    }

    return parts.length > 0 ? parts : text
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_id: videoId,
          message: input,
          conversation_history: messages
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to get response')
      }

      const data = await response.json()

      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString(),
        timestamps: data.timestamps
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
      <div className="chat-header">
        <h2>
          <SmartToyIcon sx={{ fontSize: '1.2rem', verticalAlign: 'middle', marginRight: '0.5rem' }} />
          AI Learning Assistant
        </h2>
        <p>Get instant answers from the KT session</p>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <p>
              <WavingHandIcon sx={{ fontSize: '1.1rem', verticalAlign: 'middle', marginRight: '0.3rem' }} />
              Welcome to your KT Video Assistant!
            </p>
            <p>I'm here to help you learn from this knowledge transfer video. Ask me anything about the content, and I'll provide answers with precise timestamps!</p>
            <div className="example-questions">
              <p><strong>Example questions:</strong></p>
              <ul>
                <li>"What technologies are covered in this session?"</li>
                <li>"How do I set up the development environment?"</li>
                <li>"Explain the architecture discussed"</li>
                <li>"What are the best practices mentioned?"</li>
              </ul>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">
              <div className="message-text">
                {message.role === 'assistant' ? (
                  <ReactMarkdown
                    components={{
                      // Custom text renderer to make timestamps clickable
                      p: ({ children }) => <p>{renderMessageWithClickableTimestamps(String(children))}</p>,
                      li: ({ children }) => <li>{renderMessageWithClickableTimestamps(String(children))}</li>,
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  message.content
                )}
              </div>

              {message.timestamps && message.timestamps.length > 0 && (
                <div className="timestamps-section">
                  <p className="timestamps-label">
                    <LocationOnIcon sx={{ fontSize: '0.95rem', verticalAlign: 'middle', marginRight: '0.3rem' }} />
                    Jump to relevant moments:
                  </p>
                  {message.timestamps.map((ts, idx) => (
                    <div
                      key={idx}
                      className="timestamp-chip"
                      onClick={() => onTimestampClick(ts.start_time)}
                      title={ts.text}
                    >
                      <span className="timestamp-icon">
                        <MovieIcon sx={{ fontSize: '1.1rem' }} />
                      </span>
                      <span className="timestamp-time">{formatTime(ts.start_time)}</span>
                      <span className="timestamp-preview">{ts.text}</span>
                    </div>
                  ))}
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

      <div className="chat-input-container">
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
          disabled={!input.trim() || loading}
        >
          {loading ? '...' : <SendIcon sx={{ fontSize: '1.2rem' }} />}
        </button>
      </div>
    </div>
  )
}

export default ChatInterface
