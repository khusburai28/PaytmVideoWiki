import { useState, useRef, useEffect } from 'react'
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
        <h2>🤖 AI Learning Assistant</h2>
        <p>Get instant answers from the KT session</p>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <p>👋 Welcome to your KT Video Assistant!</p>
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
              <div className="message-text">{message.content}</div>

              {message.timestamps && message.timestamps.length > 0 && (
                <div className="timestamps-section">
                  <p className="timestamps-label">Relevant moments:</p>
                  {message.timestamps.map((ts, idx) => (
                    <div
                      key={idx}
                      className="timestamp-chip"
                      onClick={() => onTimestampClick(ts.start_time)}
                      title={ts.text}
                    >
                      <span className="timestamp-icon">⏱️</span>
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
          placeholder="Ask about concepts, setup steps, best practices..."
          rows={1}
          disabled={loading}
        />
        <button
          className="send-button"
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          {loading ? '...' : '➤'}
        </button>
      </div>
    </div>
  )
}

export default ChatInterface
