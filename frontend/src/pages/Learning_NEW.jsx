import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Learning() {
  const [topic, setTopic] = useState('')
  const [text, setText] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [loading, setLoading] = useState(false)
  const [currentLesson, setCurrentLesson] = useState(null)
  const [lastFeedback, setLastFeedback] = useState(null)
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

  // Emotion emoji and color
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
      
      if (!res.ok) {
        console.error('Error:', data)
        setLoading(false)
        return
      }
      
      setSessionId(data.session_id)
      setIsSessionActive(true)
      setElapsedTime(0)
      
      // Set initial lesson
      setCurrentLesson({
        explanation: data.explanation,
        example: data.example,
        question: data.question,
        emotion: data.emotion,
        evaluation: data.evaluation,
        concept: data.current_concept,
        concept_index: data.concept_index,
        concepts_total: data.concepts_total
      })
      setLastFeedback(null)
      setText('')
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
      setCurrentLesson(null)
      setText('')
      setLastFeedback(null)
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const handleSubmit = async () => {
    if (!text.trim() || !sessionId) return
    setLoading(true)
    
    try {
      const userId = localStorage.getItem('user_id')
      const res = await fetch('/api/learning/learn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text,
          user_id: userId,
          session_id: sessionId,
          topic
        }),
      })

      const data = await res.json()
      
      // Update lesson with new response
      setCurrentLesson({
        explanation: data.explanation,
        example: data.example,
        question: data.question,
        emotion: data.emotion,
        evaluation: data.evaluation,
        feedback: data.feedback,
        intent: data.intent,
        concept: data.concept,
        concept_index: data.concept_index,
        concepts_total: data.concepts_total,
        status: data.status
      })
      
      // Show feedback
      setLastFeedback({
        emotions: data.emotion,
        evaluation: data.evaluation,
        feedback: data.feedback,
        intent: data.intent
      })
      
      setText('')
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleQuickButton = (action) => {
    switch(action) {
      case 'again':
        setText('Can you explain that again?')
        break
      case 'confused':
        setText('I don\'t understand')
        break
      case 'got_it':
        setText('Got it!')
        break
      case 'next':
        setText('Next concept')
        break
    }
  }

  if (!isSessionActive) {
    return (
      <div style={styles.startScreen}>
        <div style={styles.startCard}>
          <h1 style={styles.startTitle}>Learn with AI Tutor</h1>
          <p style={styles.startSubtitle}>What do you want to learn today?</p>
          
          <input
            type="text"
            placeholder="e.g., Recursion, Photosynthesis, French Verbs..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={styles.startInput}
            onKeyPress={(e) => e.key === 'Enter' && handleStartSession()}
          />
          
          <button
            onClick={handleStartSession}
            disabled={!topic.trim() || loading}
            style={{...styles.button, ...styles.primaryButton, opacity: !topic.trim() ? 0.5 : 1}}
          >
            {loading ? 'Starting...' : 'Start Learning'}
          </button>
        </div>
      </div>
    )
  }

  const emotionStyle = currentLesson ? getEmotionStyle(currentLesson.emotion) : getEmotionStyle('neutral')
  const progress = currentLesson ? Math.round((currentLesson.concept_index / currentLesson.concepts_total) * 100) : 0

  return (
    <div style={styles.container}>
      {/* HEADER BAR */}
      <div style={styles.headerBar}>
        <div style={styles.headerContent}>
          <div style={styles.headerItem}>
            <span style={styles.headerLabel}>Topic</span>
            <span style={styles.headerValue}>{topic}</span>
          </div>
          <div style={styles.headerItem}>
            <span style={styles.headerLabel}>Time</span>
            <span style={styles.headerValue}>{formatTime(elapsedTime)}</span>
          </div>
          <div style={styles.headerItem}>
            <span style={styles.headerLabel}>Concept</span>
            <span style={styles.headerValue}>{currentLesson?.concept_index + 1}/{currentLesson?.concepts_total}</span>
          </div>
          <button onClick={handleEndSession} style={styles.endButton}>End</button>
        </div>
      </div>

      {/* PROGRESS BAR */}
      <div style={styles.progressContainer}>
        <div style={styles.progressBar}>
          <div style={{...styles.progressFill, width: `${progress}%`}} />
        </div>
        <span style={styles.progressText}>{progress}% Complete</span>
      </div>

      {/* MAIN CONTENT */}
      <div style={styles.mainContent}>
        {/* EMOTION & FEEDBACK SECTION */}
        {lastFeedback && (
          <div style={styles.feedbackCard}>
            <div style={styles.feedbackHeader}>
              <span style={styles.emotionIndicator}>{emotionStyle.emoji}</span>
              <span style={styles.feedbackTitle}>{lastFeedback.feedback || 'Keep going!'}</span>
            </div>
            {lastFeedback.evaluation && (
              <div style={styles.feedbackDetails}>
                <span style={styles.evaluationBadge}>
                  {lastFeedback.evaluation === 'correct' && '✅ Correct!'}
                  {lastFeedback.evaluation === 'partial' && '📌 Partially Correct'}
                  {lastFeedback.evaluation === 'incorrect' && '❌ Needs Improvement'}
                </span>
              </div>
            )}
          </div>
        )}

        {/* LESSON CARD */}
        {currentLesson && (
          <div style={styles.lessonCard}>
            <div style={styles.lessonHeader}>
              <h2 style={styles.lessonConcept}>{currentLesson.concept}</h2>
              <div style={styles.emotionBadge}>
                <span style={styles.emotionEmoji}>{emotionStyle.emoji}</span>
                <span style={styles.emotionLabel}>{emotionStyle.label}</span>
              </div>
            </div>

            {/* EXPLANATION */}
            <div style={styles.lessonSection}>
              <h3 style={styles.sectionTitle}>📘 Explanation</h3>
              <p style={styles.sectionContent}>{currentLesson.explanation}</p>
            </div>

            {/* EXAMPLE */}
            <div style={styles.lessonSection}>
              <h3 style={styles.sectionTitle}>📌 Example</h3>
              <p style={styles.sectionContent}>{currentLesson.example}</p>
            </div>

            {/* QUESTION */}
            <div style={styles.lessonSection}>
              <h3 style={styles.sectionTitle}>❓ Your Turn</h3>
              <p style={styles.sectionContent}>{currentLesson.question}</p>
            </div>
          </div>
        )}

        {/* INPUT SECTION */}
        <div style={styles.inputSection}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type your answer here..."
            style={styles.textarea}
            rows="3"
            disabled={loading}
            onKeyPress={(e) => e.ctrlKey && e.key === 'Enter' && handleSubmit()}
          />
          
          {/* ACTION BUTTONS */}
          <div style={styles.buttonGroup}>
            <button
              onClick={handleSubmit}
              disabled={!text.trim() || loading}
              style={{...styles.button, ...styles.submitButton}}
            >
              {loading ? '⏳ Processing...' : '✓ Submit Answer'}
            </button>
          </div>

          {/* QUICK BUTTONS */}
          <div style={styles.quickButtons}>
            <button onClick={() => handleQuickButton('again')} style={styles.quickButton}>
              Explain Again
            </button>
            <button onClick={() => handleQuickButton('confused')} style={styles.quickButton}>
              I'm Confused
            </button>
            <button onClick={() => handleQuickButton('got_it')} style={styles.quickButton}>
              Got It!
            </button>
          </div>
        </div>
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
    borderRadius: '12px',
    padding: '40px',
    maxWidth: '500px',
    width: '90%'
  },
  
  startTitle: {
    fontSize: '32px',
    fontWeight: 'bold',
    marginBottom: '16px',
    color: '#06b6d4'
  },
  
  startSubtitle: {
    fontSize: '16px',
    color: '#94a3b8',
    marginBottom: '24px'
  },
  
  startInput: {
    width: '100%',
    padding: '12px 16px',
    fontSize: '14px',
    border: '1px solid #475569',
    borderRadius: '8px',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    marginBottom: '16px',
    boxSizing: 'border-box'
  },

  headerBar: {
    backgroundColor: '#1e293b',
    borderBottom: '2px solid #06b6d4',
    padding: '16px',
    maxHeight: '70px'
  },
  
  headerContent: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    maxWidth: '1200px',
    margin: '0 auto'
  },
  
  headerItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center'
  },
  
  headerLabel: {
    fontSize: '12px',
    color: '#64748b',
    textTransform: 'uppercase'
  },
  
  headerValue: {
    fontSize: '18px',
    fontWeight: 'bold',
    color: '#06b6d4'
  },
  
  endButton: {
    padding: '8px 24px',
    backgroundColor: '#ef4444',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '14px',
    transition: 'background-color 0.3s'
  },

  progressContainer: {
    backgroundColor: '#1e293b',
    padding: '16px',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%',
    boxSizing: 'border-box'
  },
  
  progressBar: {
    width: '100%',
    height: '8px',
    backgroundColor: '#475569',
    borderRadius: '4px',
    overflow: 'hidden',
    marginBottom: '8px'
  },
  
  progressFill: {
    height: '100%',
    backgroundColor: '#06b6d4',
    transition: 'width 0.3s ease'
  },
  
  progressText: {
    fontSize: '12px',
    color: '#94a3b8'
  },

  mainContent: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%',
    boxSizing: 'border-box'
  },

  feedbackCard: {
    backgroundColor: '#0f766e',
    border: '2px solid #14b8a6',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '24px'
  },
  
  feedbackHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  
  emotionIndicator: {
    fontSize: '24px'
  },
  
  feedbackTitle: {
    fontSize: '16px',
    fontWeight: 'bold',
    color: '#14b8a6'
  },
  
  feedbackDetails: {
    marginTop: '8px',
    paddingTop: '8px',
    borderTop: '1px solid rgba(20, 184, 166, 0.3)'
  },
  
  evaluationBadge: {
    display: 'inline-block',
    padding: '4px 12px',
    backgroundColor: 'rgba(20, 184, 166, 0.2)',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 'bold',
    color: '#14b8a6'
  },

  lessonCard: {
    backgroundColor: '#1e293b',
    border: '2px solid #06b6d4',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '24px'
  },
  
  lessonHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid #475569'
  },
  
  lessonConcept: {
    fontSize: '24px',
    fontWeight: 'bold',
    color: '#06b6d4',
    margin: 0
  },
  
  emotionBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'rgba(6, 182, 212, 0.1)',
    padding: '8px 16px',
    borderRadius: '20px'
  },
  
  emotionEmoji: {
    fontSize: '20px'
  },
  
  emotionLabel: {
    fontSize: '12px',
    fontWeight: 'bold',
    color: '#06b6d4'
  },

  lessonSection: {
    marginBottom: '24px'
  },
  
  sectionTitle: {
    fontSize: '16px',
    fontWeight: 'bold',
    color: '#94a3b8',
    marginBottom: '12px',
    margin: '0 0 12px 0'
  },
  
  sectionContent: {
    fontSize: '15px',
    lineHeight: '1.6',
    color: '#cbd5e1',
    margin: 0
  },

  inputSection: {
    backgroundColor: '#1e293b',
    border: '2px solid #475569',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '24px'
  },
  
  textarea: {
    width: '100%',
    padding: '12px',
    fontSize: '14px',
    border: '1px solid #475569',
    borderRadius: '6px',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontFamily: 'inherit',
    marginBottom: '16px',
    boxSizing: 'border-box',
    resize: 'vertical'
  },
  
  buttonGroup: {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px'
  },
  
  button: {
    padding: '12px 24px',
    fontSize: '14px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold',
    transition: 'all 0.3s'
  },
  
  submitButton: {
    backgroundColor: '#22c55e',
    color: 'white',
    flex: 1
  },
  
  primaryButton: {
    backgroundColor: '#06b6d4',
    color: 'white',
    width: '100%'
  },
  
  quickButtons: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap'
  },
  
  quickButton: {
    padding: '8px 16px',
    fontSize: '12px',
    backgroundColor: '#334155',
    color: '#94a3b8',
    border: '1px solid #475569',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'all 0.3s'
  }
}

export default Learning
