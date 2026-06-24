import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Learning() {
  const [topic, setTopic] = useState('')
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState([])
  const [emotion, setEmotion] = useState('neutral')
  const navigate = useNavigate()

  // Timer effect
  useEffect(() => {
    let interval
    if (isSessionActive) {
      interval = setInterval(() => {
        setElapsedTime(prev => prev + 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [isSessionActive])

  const formatTime = (seconds) => {
    const hrs = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  const getEmotionStyle = (emotion) => {
    const emotionMap = {
      'very_frustrated': { emoji: '😭', color: '#ef4444', label: 'Very Frustrated' },
      'frustrated': { emoji: '😤', color: '#f97316', label: 'Frustrated' },
      'confused': { emoji: '😕', color: '#eab308', label: 'Confused' },
      'neutral': { emoji: '😐', color: '#64748b', label: 'Neutral' },
      'engaged': { emoji: '😊', color: '#22c55e', label: 'Engaged' },
      'very_engaged': { emoji: '🤓', color: '#06b6d4', label: 'Very Engaged' }
    }
    return emotionMap[emotion?.toLowerCase()] || emotionMap['neutral']
  }

  const handleStartSession = async () => {
    if (!topic.trim()) return
    
    setLoading(true)
    try {
      const userId = localStorage.getItem('user_id')
      
      const res = await fetch('/api/session/start-teaching', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, topic }),
      })

      const data = await res.json()
      
      if (!res.ok || data.error) {
        console.error('Error:', data)
        setLoading(false)
        return
      }
      
      setSessionId(data.session_id)
      setIsSessionActive(true)
      setElapsedTime(0)
      
      // Add AI's initial message to chat
      const initialMessage = {
        role: 'assistant',
        content: `${data.explanation}\n\n${data.example}\n\n${data.question}`
      }
      setMessages([initialMessage])
      setInput('')
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEndSession = async () => {
    if (!sessionId) return

    try {
      await fetch('/api/session/end', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })

      setIsSessionActive(false)
      setSessionId(null)
      setTopic('')
      setElapsedTime(0)
      setMessages([])
      setInput('')
      setEmotion('neutral')
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const handleSubmit = async () => {
    if (!input.trim() || !sessionId) return
    
    // Add user message to UI immediately
    const userMessage = {
      role: 'user',
      content: input
    }
    setMessages(prev => [...prev, userMessage])
    setLoading(true)
    
    try {
      const res = await fetch('/api/session/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          session_id: sessionId,
          text: input
        }),
      })

      const data = await res.json()
      
      if (data.error) {
        console.error('Error:', data)
        setLoading(false)
        setInput('')
        return
      }

      // Add AI response to chat
      const aiMessage = {
        role: 'assistant',
        content: data.response
      }
      setMessages(prev => [...prev, aiMessage])
      setEmotion(data.emotion || 'neutral')
      setInput('')
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!isSessionActive) {
    return (
      <div style={styles.startScreen}>
        <div style={styles.startCard}>
          <h1 style={styles.startTitle}>📚 EchoConnect</h1>
          <p style={styles.startSubtitle}>Your AI Tutoring Assistant</p>
          
          <input
            type="text"
            placeholder="What topic do you want to learn today?"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={styles.startInput}
            onKeyPress={(e) => e.key === 'Enter' && handleStartSession()}
          />
          
          <button
            onClick={handleStartSession}
            disabled={!topic.trim() || loading}
            style={{...styles.button, ...styles.primaryButton}}
          >
            {loading ? 'Starting...' : 'Start Learning'}
          </button>
        </div>
      </div>
    )
  }

  const emotionStyle = getEmotionStyle(emotion)

  return (
    <div style={styles.container}>
      {/* HEADER */}
      <div style={styles.header}>
        <div style={styles.headerContent}>
          <div>
            <h2 style={styles.headerTitle}>{topic}</h2>
            <span style={styles.timeDisplay}>{formatTime(elapsedTime)}</span>
          </div>
          <div style={styles.emotionDisplay}>
            <span style={styles.emotionEmoji}>{emotionStyle.emoji}</span>
            <span style={styles.emotionText}>{emotionStyle.label}</span>
          </div>
          <button onClick={handleEndSession} style={styles.endButton}>Exit</button>
        </div>
      </div>

      {/* CHAT AREA */}
      <div style={styles.chatContainer}>
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={msg.role === 'user' ? styles.userMessageWrapper : styles.aiMessageWrapper}
          >
            <div
              style={msg.role === 'user' ? styles.userMessage : styles.aiMessage}
            >
              <p style={styles.messageText}>{msg.content}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div style={styles.aiMessageWrapper}>
            <div style={styles.typingIndicator}>
              <span style={styles.typingDot}></span>
              <span style={styles.typingDot}></span>
              <span style={styles.typingDot}></span>
              <span style={{ fontSize: '12px', marginLeft: '8px', color: '#94a3b8' }}>
                EchoConnect is typing...
              </span>
            </div>
          </div>
        )}
      </div>

      {/* INPUT AREA */}
      <div style={styles.inputArea}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your response or ask a question..."
          style={styles.input}
          rows="2"
          disabled={loading}
          onKeyPress={(e) => e.ctrlKey && e.key === 'Enter' && handleSubmit()}
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || loading}
          style={styles.sendButton}
        >
          {loading ? '...' : '→ Send'}
        </button>
      </div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#0f172a',
    color: '#e2e8f0'
  },

  startScreen: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    backgroundColor: '#0f172a'
  },

  startCard: {
    backgroundColor: '#1e293b',
    border: '2px solid #06b6d4',
    borderRadius: '16px',
    padding: '48px',
    maxWidth: '500px',
    width: '90%',
    textAlign: 'center',
    boxShadow: '0 8px 32px rgba(6, 182, 212, 0.2)'
  },

  startTitle: {
    fontSize: '36px',
    fontWeight: 'bold',
    marginBottom: '12px',
    color: '#06b6d4'
  },

  startSubtitle: {
    fontSize: '16px',
    color: '#94a3b8',
    marginBottom: '32px'
  },

  startInput: {
    width: '100%',
    padding: '14px',
    fontSize: '14px',
    border: '1px solid #475569',
    borderRadius: '8px',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    marginBottom: '16px',
    boxSizing: 'border-box'
  },

  button: {
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '14px',
    transition: 'all 0.3s'
  },

  primaryButton: {
    width: '100%',
    padding: '14px',
    backgroundColor: '#06b6d4',
    color: '#0f172a'
  },

  header: {
    backgroundColor: '#1e293b',
    borderBottom: '2px solid #06b6d4',
    padding: '16px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)'
  },

  headerContent: {
    maxWidth: '1200px',
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },

  headerTitle: {
    fontSize: '20px',
    fontWeight: 'bold',
    margin: '0 0 4px 0',
    color: '#06b6d4'
  },

  timeDisplay: {
    fontSize: '12px',
    color: '#94a3b8'
  },

  emotionDisplay: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'rgba(6, 182, 212, 0.1)',
    padding: '8px 16px',
    borderRadius: '20px'
  },

  emotionEmoji: {
    fontSize: '18px'
  },

  emotionText: {
    fontSize: '12px',
    color: '#06b6d4',
    fontWeight: 'bold'
  },

  endButton: {
    padding: '8px 16px',
    backgroundColor: '#ef4444',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '12px'
  },

  chatContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
    maxWidth: '1000px',
    margin: '0 auto',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
  },

  userMessageWrapper: {
    display: 'flex',
    justifyContent: 'flex-end'
  },

  aiMessageWrapper: {
    display: 'flex',
    justifyContent: 'flex-start'
  },

  userMessage: {
    backgroundColor: '#06b6d4',
    color: '#0f172a',
    padding: '12px 16px',
    borderRadius: '12px',
    maxWidth: '70%',
    wordWrap: 'break-word'
  },

  aiMessage: {
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    color: '#cbd5e1',
    padding: '12px 16px',
    borderRadius: '12px',
    maxWidth: '70%',
    wordWrap: 'break-word'
  },

  messageText: {
    margin: '0',
    fontSize: '14px',
    lineHeight: '1.5'
  },

  typingIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    padding: '12px 16px',
    borderRadius: '12px',
    maxWidth: '200px'
  },

  typingDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#06b6d4',
    animation: 'pulse 1.4s infinite',
    display: 'inline-block'
  },

  inputArea: {
    backgroundColor: '#1e293b',
    borderTop: '2px solid #475569',
    padding: '16px',
    maxWidth: '1000px',
    margin: '0 auto',
    width: '100%',
    boxSizing: 'border-box',
    display: 'flex',
    gap: '12px'
  },

  input: {
    flex: 1,
    padding: '12px',
    backgroundColor: '#0f172a',
    border: '1px solid #475569',
    borderRadius: '8px',
    color: '#e2e8f0',
    fontSize: '14px',
    fontFamily: 'inherit',
    resize: 'none'
  },

  sendButton: {
    padding: '12px 24px',
    backgroundColor: '#22c55e',
    color: '#0f172a',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '14px',
    transition: 'all 0.3s'
  }
}

// Add CSS animation for typing indicator
const styleSheet = document.createElement('style')
styleSheet.textContent = `
  @keyframes pulse {
    0%, 60%, 100% {
      opacity: 0.3;
    }
    30% {
      opacity: 1;
    }
  }
`
document.head.appendChild(styleSheet)

export default Learning
