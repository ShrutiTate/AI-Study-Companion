import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function History() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSession, setSelectedSession] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('echoTheme') || 'dark')
  const [fontSize, setFontSize] = useState(() => parseInt(localStorage.getItem('echoFontSize')) || 16)
  const [filter, setFilter] = useState('all') // all, active, completed
  const navigate = useNavigate()

  // Fetch session history on mount
  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      setError(null)
      const userId = localStorage.getItem('user_id')
      console.log('[HISTORY] Fetching for user_id:', userId)
      
      if (!userId) {
        const msg = 'No user_id in localStorage - redirecting to login'
        console.error('[HISTORY]', msg)
        setError(msg)
        navigate('/login')
        return
      }

      console.log('[HISTORY] Fetching from: /api/session/history/' + userId)
      const res = await fetch(`/api/session/history/${userId}`)
      
      console.log('[HISTORY] Response status:', res.status, res.statusText)
      
      if (!res.ok) {
        const msg = `HTTP error: ${res.status}`
        console.error('[HISTORY]', msg)
        setError(msg)
        setSessions([])
        setLoading(false)
        return
      }

      const data = await res.json()
      console.log('[HISTORY] Full response:', JSON.stringify(data, null, 2))

      if (data.sessions && Array.isArray(data.sessions)) {
        console.log('[HISTORY] SUCCESS - Sessions loaded:', data.sessions.length)
        setSessions(data.sessions)
      } else {
        const msg = 'Invalid response format: no sessions array'
        console.warn('[HISTORY]', msg, data)
        setError(msg)
        setSessions([])
      }
      setLoading(false)
    } catch (error) {
      const msg = `Fetch error: ${error.message}`
      console.error('[HISTORY]', msg, error)
      setError(msg)
      setSessions([])
      setLoading(false)
    }
  }

  const handleResumeSession = async (sessionId) => {
    console.log('[HISTORY] ➡️  RESUME BUTTON CLICKED for:', sessionId)
    try {
      const res = await fetch(`/api/session/resume/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      const data = await res.json()

      console.log('[HISTORY] Resume API response:', data)

      if (data.status === 'success' || !data.error) {
        // Navigate to Learning with resumed session
        console.log('[HISTORY] ✅ Session resumed successfully')
        console.log('[HISTORY] 📍 Navigating to /learning with state:', { resumeSessionId: sessionId })
        navigate('/learning', { state: { resumeSessionId: sessionId } })
        console.log('[HISTORY] ✅ Navigation initiated')
      } else {
        console.error('[HISTORY] ❌ Resume failed:', data.error)
        alert('Failed to resume session: ' + (data.error || 'Unknown error'))
      }
    } catch (error) {
      console.error('[HISTORY] ❌ Error resuming session:', error)
      alert('Error resuming session: ' + error.message)
    }
  }

  const handleDeleteSession = async (sessionId) => {
    if (!window.confirm('Are you sure you want to delete this session? This cannot be undone.')) {
      return
    }

    try {
      const res = await fetch(`/api/session/${sessionId}`, {
        method: 'DELETE'
      })
      const data = await res.json()

      if (data.status === 'success') {
        setSessions(sessions.filter(s => s.session_id !== sessionId))
        setSelectedSession(null)
        alert('Session deleted successfully')
      } else {
        alert('Failed to delete session')
      }
    } catch (error) {
      console.error('Error deleting session:', error)
      alert('Error deleting session')
    }
  }

  const handleViewDetails = (session) => {
    setSelectedSession(session.session_id)
  }

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A'
    const date = new Date(isoString)
    return date.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' ' + date.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true })
  }

  const formatDuration = (seconds) => {
    if (!seconds) return '0 min'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }

  const getEmotionEmoji = (emotion) => {
    const emotionMap = {
      'very_frustrated': '😭',
      'frustrated': '😤',
      'confused': '😕',
      'neutral': '😐',
      'engaged': '😊',
      'very_engaged': '🤓'
    }
    return emotionMap[emotion?.toLowerCase()] || '😐'
  }

  const getColorForStatus = (status) => {
    return status === 'active' ? '#22c55e' : status === 'completed' ? '#3b82f6' : '#ef4444'
  }

  const getThemeColors = () => {
    return theme === 'dark' ? {
      bg: '#0f172a',
      bgSecondary: '#1e293b',
      border: '#475569',
      text: '#e2e8f0',
      textMuted: '#94a3b8',
      accent: '#06b6d4',
      hoverBg: '#334155'
    } : {
      bg: '#f8fafc',
      bgSecondary: '#f1f5f9',
      border: '#cbd5e1',
      text: '#1e293b',
      textMuted: '#475569',
      accent: '#0891b2',
      hoverBg: '#e2e8f0'
    }
  }

  const colors = getThemeColors()

  const filteredSessions = sessions.filter(session => {
    if (filter === 'active') return session.status === 'active'
    if (filter === 'completed') return session.status === 'completed'
    return true
  })

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: colors.bg,
        color: colors.text,
        fontSize: `${fontSize}px`
      }}>
        <div style={{textAlign: 'center'}}>
          <div>Loading session history...</div>
          {error && <div style={{color: 'red', marginTop: '10px'}}>Error: {error}</div>}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: colors.bg,
        color: colors.text,
        fontSize: `${fontSize}px`
      }}>
        <div style={{textAlign: 'center', color: 'red'}}>
          <div>Error loading sessions</div>
          <div style={{marginTop: '10px', fontSize: `${fontSize - 2}px`}}>{error}</div>
          <button onClick={fetchHistory} style={{marginTop: '20px', padding: '8px 16px', cursor: 'pointer'}}>Retry</button>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: colors.bg,
      color: colors.text,
      fontSize: `${fontSize}px`,
      padding: '20px'
    }}>
      {/* Debug Info */}
      <div style={{
        position: 'fixed',
        bottom: '10px',
        right: '10px',
        backgroundColor: 'rgba(0,0,0,0.8)',
        color: error ? '#f00' : '#0f0',
        padding: '10px',
        borderRadius: '4px',
        fontSize: '11px',
        fontFamily: 'monospace',
        maxWidth: '350px',
        zIndex: 9999
      }}>
        <div>Sessions: {sessions.length}</div>
        <div>Filtered: {filteredSessions.length}</div>
        <div>Filter: {filter}</div>
        <div>Selected: {selectedSession ? 'yes' : 'no'}</div>
        {error && <div style={{color: '#f00', marginTop: '5px'}}>ERROR: {error}</div>}
      </div>
      
      {/* Header */}
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        marginBottom: '30px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          gap: '10px'
        }}>
          <h1 style={{
            margin: '0',
            color: colors.accent,
            fontSize: `${fontSize + 8}px`
          }}>📚 Session History</h1>
          <div style={{display: 'flex', gap: '10px'}}>
            <button
              onClick={fetchHistory}
              title="Refresh session list"
              style={{
                padding: '10px 15px',
                backgroundColor: colors.bgSecondary,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: `${fontSize}px`,
                fontWeight: 'bold'
              }}
            >
              🔄 Refresh
            </button>
            <button
              onClick={() => navigate('/learning')}
              style={{
                padding: '10px 20px',
                backgroundColor: colors.accent,
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: `${fontSize}px`
              }}
            >
              + New Session
            </button>
          </div>
        </div>

        {/* Stats */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '15px',
          marginBottom: '20px'
        }}>
          <div style={{
            backgroundColor: colors.bgSecondary,
            padding: '15px',
            borderRadius: '8px',
            border: `1px solid ${colors.border}`
          }}>
            <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Total Sessions</p>
            <p style={{ margin: '0', color: colors.accent, fontSize: `${fontSize + 4}px`, fontWeight: 'bold' }}>
              {sessions.length}
            </p>
          </div>
          <div style={{
            backgroundColor: colors.bgSecondary,
            padding: '15px',
            borderRadius: '8px',
            border: `1px solid ${colors.border}`
          }}>
            <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Active Sessions</p>
            <p style={{ margin: '0', color: '#22c55e', fontSize: `${fontSize + 4}px`, fontWeight: 'bold' }}>
              {sessions.filter(s => s.status === 'active').length}
            </p>
          </div>
          <div style={{
            backgroundColor: colors.bgSecondary,
            padding: '15px',
            borderRadius: '8px',
            border: `1px solid ${colors.border}`
          }}>
            <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Completed</p>
            <p style={{ margin: '0', color: '#3b82f6', fontSize: `${fontSize + 4}px`, fontWeight: 'bold' }}>
              {sessions.filter(s => s.status === 'completed').length}
            </p>
          </div>
        </div>

        {/* Filter buttons */}
        <div style={{
          display: 'flex',
          gap: '10px',
          marginBottom: '20px'
        }}>
          {['all', 'active', 'completed'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '8px 16px',
                backgroundColor: filter === f ? colors.accent : colors.bgSecondary,
                color: filter === f ? '#fff' : colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: `${fontSize}px`,
                textTransform: 'capitalize'
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Sessions list and details */}
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        display: 'grid',
        gridTemplateColumns: selectedSession ? '1fr 1fr' : '1fr',
        gap: '20px'
      }}>
        {/* Sessions Table */}
        <div style={{
          backgroundColor: colors.bgSecondary,
          borderRadius: '12px',
          border: `1px solid ${colors.border}`,
          overflow: 'hidden'
        }}>
          <div style={{padding: '15px', color: colors.textMuted, fontSize: '12px'}}>
            [{sessions.length} total sessions] [filter: {filter}]
          </div>
          
          {filteredSessions.length === 0 ? (
            <div style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: colors.textMuted
            }}>
              <p>
                {sessions.length === 0 
                  ? '📚 No sessions yet. Start learning to create your first session!' 
                  : `No ${filter !== 'all' ? filter : ''} sessions found`}
              </p>
            </div>
          ) : (
            <div>
              {/* Header row */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr 1fr 1.5fr 100px',
                gap: '15px',
                padding: '15px',
                backgroundColor: colors.bgSecondary,
                borderBottom: `2px solid ${colors.border}`,
                fontWeight: 'bold',
                fontSize: `${fontSize - 1}px`,
                color: colors.accent
              }}>
                <div>Topic</div>
                <div>Status</div>
                <div>Messages</div>
                <div>Date</div>
                <div>Action</div>
              </div>

              {/* Session rows */}
              {filteredSessions.map((session, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 1fr 1fr 1.5fr 100px',
                    gap: '15px',
                    padding: '15px',
                    borderBottom: `1px solid ${colors.border}`,
                    alignItems: 'center',
                    backgroundColor: selectedSession === session.session_id ? `rgba(6, 182, 212, 0.1)` : 'transparent',
                    cursor: 'pointer',
                    transition: 'background-color 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    if (selectedSession !== session.session_id) {
                      e.currentTarget.style.backgroundColor = colors.hoverBg
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedSession !== session.session_id) {
                      e.currentTarget.style.backgroundColor = 'transparent'
                    }
                  }}
                  onClick={() => handleViewDetails(session)}
                >
                  <div style={{ fontWeight: selectedSession === session.session_id ? 'bold' : 'normal' }}>
                    {session.topic}
                  </div>
                  <div style={{ color: getColorForStatus(session.status), fontWeight: 'bold' }}>
                    {session.status === 'active' ? '🟢 Active' : '✓ Ended'}
                  </div>
                  <div>{session.message_count} messages</div>
                  <div style={{ fontSize: `${fontSize - 1}px`, color: colors.textMuted }}>
                    {formatDate(session.start_time)}
                  </div>
                  <div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (session.status === 'completed') {
                          handleResumeSession(session.session_id)
                        } else {
                          navigate('/learning', { state: { sessionId: session.session_id } })
                        }
                      }}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: session.status === 'completed' ? '#22c55e' : colors.accent,
                        color: '#fff',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: `${fontSize - 1}px`,
                        fontWeight: 'bold'
                      }}
                    >
                      {session.status === 'completed' ? 'Resume' : 'Continue'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Session Details Panel */}
        {selectedSession && (
          <div style={{
            backgroundColor: colors.bgSecondary,
            borderRadius: '12px',
            border: `2px solid ${colors.accent}`,
            padding: '20px',
            maxHeight: '600px',
            overflowY: 'auto'
          }}>
            {(() => {
              const session = filteredSessions.find(s => s.session_id === selectedSession)
              return session ? (
                <>
                  <h2 style={{ margin: '0 0 20px 0', color: colors.accent }}>📋 Session Details</h2>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Topic</p>
                      <p style={{ margin: '0', color: colors.text, fontWeight: 'bold' }}>{session.topic}</p>
                    </div>

                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Status</p>
                      <p style={{
                        margin: '0',
                        color: getColorForStatus(session.status),
                        fontWeight: 'bold'
                      }}>
                        {session.status === 'active' ? '🟢 Active' : '✓ Completed'}
                      </p>
                    </div>

                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Started</p>
                      <p style={{ margin: '0', color: colors.text }}>{formatDate(session.start_time)}</p>
                    </div>

                    {session.end_time && (
                      <div>
                        <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Ended</p>
                        <p style={{ margin: '0', color: colors.text }}>{formatDate(session.end_time)}</p>
                      </div>
                    )}

                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Duration</p>
                      <p style={{ margin: '0', color: colors.text, fontWeight: 'bold' }}>{formatDuration(session.duration)}</p>
                    </div>

                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Messages Count</p>
                      <p style={{ margin: '0', color: colors.text, fontWeight: 'bold' }}>{session.message_count}</p>
                    </div>

                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Last Emotion</p>
                      <p style={{ margin: '0', fontSize: '24px' }}>
                        {getEmotionEmoji(session.emotion)} {session.emotion}
                      </p>
                    </div>

                    <div>
                      <p style={{ margin: '0 0 5px 0', color: colors.textMuted, fontSize: `${fontSize - 2}px` }}>Current Concept</p>
                      <p style={{ margin: '0', color: colors.text }}>{session.current_concept}</p>
                    </div>

                    {/* Action Buttons */}
                    <div style={{
                      display: 'flex',
                      gap: '10px',
                      marginTop: '20px',
                      borderTop: `1px solid ${colors.border}`,
                      paddingTop: '20px'
                    }}>
                      <button
                        onClick={() => {
                          if (session.status === 'completed') {
                            handleResumeSession(session.session_id)
                          } else {
                            navigate('/learning', { state: { sessionId: session.session_id } })
                          }
                        }}
                        style={{
                          flex: 1,
                          padding: '10px',
                          backgroundColor: session.status === 'completed' ? '#22c55e' : colors.accent,
                          color: '#fff',
                          border: 'none',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontWeight: 'bold'
                        }}
                      >
                        {session.status === 'completed' ? '▶️ Resume' : '➤ Continue'}
                      </button>
                      <button
                        onClick={() => handleDeleteSession(session.session_id)}
                        style={{
                          flex: 1,
                          padding: '10px',
                          backgroundColor: '#ef4444',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontWeight: 'bold'
                        }}
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                </>
              ) : null
            })()}
          </div>
        )}
      </div>
    </div>
  )
}

export default History
