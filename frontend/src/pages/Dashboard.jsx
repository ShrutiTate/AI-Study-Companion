import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

function Dashboard() {
  const [user, setUser] = useState(null)
  const [data, setData] = useState(null)
  const [stats, setStats] = useState({ sessions: 0, focus: null, streak: 0 })
  const [hoveredBtn, setHoveredBtn] = useState(null)
  const [hoveredCard, setHoveredCard] = useState(null)
  const [hoveredStat, setHoveredStat] = useState(null)
  const [showProfilePanel, setShowProfilePanel] = useState(false)
  const theme = 'dark'
  const [fontSize, setFontSize] = useState(localStorage.getItem('fontSize') || '16')
  const [lastSessionSummary, setLastSessionSummary] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    localStorage.setItem('fontSize', fontSize)
  }, [fontSize])

  // Check for last session summary from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('lastSessionSummary')
    if (saved) {
      try {
        setLastSessionSummary(JSON.parse(saved))
        // Clear after showing so it doesn't persist forever
        setTimeout(() => {
          localStorage.removeItem('lastSessionSummary')
          localStorage.removeItem('lastSessionSummaryTime')
          setLastSessionSummary(null)
        }, 60000) // Clear after 1 minute
      } catch (e) {
        console.error('Error parsing session summary:', e)
      }
    }
  }, [location])

  // Fetch analytics data
  const fetchAnalytics = (userId) => {
    if (!userId) return
    
    fetch(`/api/learning/analytics?user_id=${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
      .then(res => res.json())
      .then(analyticsData => {
        setData(analyticsData)
        
        // Calculate focus score with validation
        const engaged = analyticsData?.engaged || 0
        const confused = analyticsData?.confused || 0
        const frustrated = analyticsData?.frustrated || 0
        const neutral = analyticsData?.neutral || 0
        const totalEmotionEvents = engaged + confused + frustrated + neutral
        
        let focus = null
        if (totalEmotionEvents > 0) {
          const positiveScore = engaged + neutral * 0.5
          const negativeScore = frustrated + confused * 0.75
          const normalized = (positiveScore - negativeScore) / totalEmotionEvents
          focus = Math.max(0, Math.min(100, Math.round(50 + normalized * 50)))
        }
        
        // Calculate streak (consecutive learning days)
        const streak = calculateStreak(analyticsData?.learning_dates || [])
        
        setStats({
          sessions: analyticsData?.total_sessions || 0,
          focus: focus,
          streak: streak
        })
      })
      .catch(err => console.error('Analytics fetch error:', err))
  }

  // Initialize user on mount
  useEffect(() => {
    const userId = localStorage.getItem('user_id')
    const name = localStorage.getItem('name')
    const email = localStorage.getItem('email') || 'guest@example.com'

    if (!userId) {
      navigate('/login')
      return
    }

    setUser({ userId, name, email })
    fetchAnalytics(userId)
  }, [navigate])

  // Auto-refresh analytics every 30 seconds
  useEffect(() => {
    const userId = localStorage.getItem('user_id')
    if (!userId) return

    const interval = setInterval(() => {
      fetchAnalytics(userId)
    }, 30000) // Refresh every 30 seconds

    return () => clearInterval(interval)
  }, [])

  // Refetch analytics when page comes into focus
  useEffect(() => {
    const userId = localStorage.getItem('user_id')
    if (!userId) return

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchAnalytics(userId)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [])

  const calculateStreak = (dates) => {
    if (!dates || dates.length === 0) return 0

    const formatDate = (date) => {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    const normalizedDates = Array.from(new Set(dates))
      .map(dateStr => dateStr.trim())
      .filter(Boolean)
      .sort()

    if (normalizedDates.length === 0) return 0

    const latestDateParts = normalizedDates[normalizedDates.length - 1].split('-').map(Number)
    let currentDate = new Date(latestDateParts[0], latestDateParts[1] - 1, latestDateParts[2])
    const dateSet = new Set(normalizedDates)

    let streak = 0
    while (dateSet.has(formatDate(currentDate))) {
      streak++
      currentDate.setDate(currentDate.getDate() - 1)
    }

    return streak
  }

  const formatTime = (minutes) => {
    if (!minutes || minutes === 0) return '0m'
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    
    if (hours === 0) return `${mins}m`
    if (mins === 0) return `${hours}h`
    return `${hours}h ${mins}m`
  }

  // Download session summary as text-based PDF (searchable, no images)
  const downloadSessionSummaryAsPDF = async () => {
    if (!lastSessionSummary) return

    const jsPDF = (await import('jspdf')).default
    const pdf = new jsPDF('p', 'mm', 'a4')
    
    let yPosition = 15
    const pageHeight = pdf.internal.pageSize.getHeight()
    const pageWidth = pdf.internal.pageSize.getWidth()
    const leftMargin = 12
    const lineHeight = 5
    const contentWidth = pageWidth - 2 * leftMargin

    // Helper function to add text with wrapping
    const addWrappedText = (text, fontSize, isBold = false, color = [0, 0, 0]) => {
      pdf.setFontSize(fontSize)
      pdf.setFont(undefined, isBold ? 'bold' : 'normal')
      pdf.setTextColor(color[0], color[1], color[2])

      const lines = pdf.splitTextToSize(text, contentWidth)
      lines.forEach(line => {
        if (yPosition > pageHeight - 12) {
          pdf.addPage()
          yPosition = 15
        }
        pdf.text(line, leftMargin, yPosition)
        yPosition += lineHeight
      })
    }

    const addSectionHeader = (title) => {
      addWrappedText(title, 11, true, [0, 100, 150])
      yPosition += 2
    }

    const addContent = (text) => {
      addWrappedText(text, 9, false, [40, 40, 40])
      yPosition += 1.5
    }

    // TITLE
    pdf.setFillColor(230, 240, 250)
    pdf.rect(12, yPosition - 4, pageWidth - 24, 10, 'F')
    addWrappedText('SESSION SUMMARY REPORT', 14, true, [0, 100, 150])
    addWrappedText('EchoConnect - AI Learning Session', 8, false, [100, 100, 100])
    yPosition += 3

    // Topic
    addSectionHeader('TOPIC STUDIED')
    addContent(lastSessionSummary.topic)
    yPosition += 2

    // Duration
    addSectionHeader('SESSION DURATION')
    addContent(`Total Time: ${lastSessionSummary.duration}`)
    addContent(`Total Seconds: ${lastSessionSummary.totalSeconds}`)
    yPosition += 2

    // Stats
    addSectionHeader('ENGAGEMENT METRICS')
    addContent(`Total Messages: ${lastSessionSummary.messagesExchanged}`)
    addContent(`Assistant Responses: ${lastSessionSummary.assistantMessagesExchanged || lastSessionSummary.messagesExchanged}`)
    addContent(`Learning Steps: ${lastSessionSummary.stepCount}`)
    addContent(`Engagement Level: ${lastSessionSummary.engagementPercent ?? Math.round((lastSessionSummary.emotionJourney.engaged / (lastSessionSummary.assistantMessagesExchanged || lastSessionSummary.messagesExchanged || 1)) * 100)}%`)
    yPosition += 2

    // Emotion Journey
    addSectionHeader('EMOTION BREAKDOWN')
    addContent(`Engaged: ${lastSessionSummary.emotionJourney.engaged} times`)
    addContent(`Neutral: ${lastSessionSummary.emotionJourney.neutral} times`)
    addContent(`Confused: ${lastSessionSummary.emotionJourney.confused} times`)
    addContent(`Frustrated: ${lastSessionSummary.emotionJourney.frustrated} times`)
    yPosition += 2

    // Key Concepts
    addSectionHeader('KEY CONCEPTS COVERED')
    lastSessionSummary.topicsLearned.forEach(concept => {
      addContent(`- ${concept}`)
    })

    // Footer
    yPosition += 3
    if (yPosition > pageHeight - 10) {
      pdf.addPage()
      yPosition = 15
    }
    addWrappedText(`Generated: ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}`, 7, false, [120, 120, 120])
    addWrappedText(`Session ID: ${lastSessionSummary.sessionId}`, 7, false, [120, 120, 120])

    pdf.save(`EchoConnect_Summary_${lastSessionSummary.topic}_${new Date().getTime()}.pdf`)
  }

  const handleLogout = () => {
    localStorage.removeItem('user_id')
    localStorage.removeItem('name')
    localStorage.removeItem('email')
    navigate('/login')
  }

  // Compute styles based on theme and fontSize
  const styles = getStyles(theme, fontSize)

  if (!user) return <div style={styles.container}><p style={{ color: 'white' }}>Loading...</p></div>

  return (
    <div style={styles.container}>
      <div style={styles.main}>
        <div style={styles.header}>
          <div style={styles.headerTop}>
            <div style={styles.headerLeft}>
              <h1 style={styles.title}>Welcome, {user.name}! 👋</h1>
              <p style={styles.subtitle}>Keep learning, stay focused, and review your progress.</p>
            </div>
            <div style={styles.headerRight}>
              <button
                type="button"
                onClick={() => setShowProfilePanel((prev) => !prev)}
                style={styles.avatarButton}
                title="Open profile settings"
              >
                <span style={styles.avatarInitial}>{user.name ? user.name.charAt(0).toUpperCase() : 'U'}</span>
              </button>
              {showProfilePanel && (
                <div style={styles.profileCard}>
                  <div style={styles.profileTitle}>Profile</div>
                  <div style={styles.profileMeta}>
                    <span style={styles.profileLabel}>Name</span>
                    <span style={styles.profileValue}>{user.name}</span>
                  </div>
                  <div style={styles.profileMeta}>
                    <span style={styles.profileLabel}>Email</span>
                    <span style={styles.profileValue}>{user.email || 'No email set'}</span>
                  </div>
                  <button
                    style={styles.profileButton}
                    onClick={() => {
                      setShowProfilePanel(false)
                      navigate('/settings')
                    }}
                  >
                    Manage settings
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        {data && data.db_status === 'offline' && (
          <div style={{marginBottom: '12px', padding: '10px 14px', borderRadius: '10px', background: 'linear-gradient(90deg, rgba(245,158,11,0.06), rgba(99,102,241,0.04))', border: '1px solid rgba(245,158,11,0.14)', color: '#f59e0b', fontWeight: 600}}>
            ⚠️ Analytics offline ({data.db_status}) — realtime stats unavailable
          </div>
        )}
        <div style={styles.statsGrid}>
          <div 
            style={{
              ...styles.statCard, 
              transform: hoveredStat === 'sessions' ? 'translateY(-4px)' : 'translateY(0)',
              borderColor: hoveredStat === 'sessions' ? 'rgba(59,130,246,0.5)' : 'rgba(59,130,246,0.2)',
            }}
            onMouseEnter={() => setHoveredStat('sessions')}
            onMouseLeave={() => setHoveredStat(null)}
          >
            <div style={styles.statLabel}>📚 Sessions</div>
            <div style={styles.statValue}>{stats.sessions}</div>
            {stats.sessions === 0 && (
              <div style={styles.emptyMessage}>Start a session to begin learning</div>
            )}
          </div>
          <div 
            style={{
              ...styles.statCard, 
              transform: hoveredStat === 'focus' ? 'translateY(-4px)' : 'translateY(0)',
              borderColor: hoveredStat === 'focus' ? 'rgba(59,130,246,0.5)' : 'rgba(59,130,246,0.2)',
            }}
            onMouseEnter={() => setHoveredStat('focus')}
            onMouseLeave={() => setHoveredStat(null)}
          >
            <div style={styles.statLabel}>🎯 Focus Score</div>
            <div style={styles.statValue}>
              {stats.focus === null ? '—' : `${stats.focus}%`}
            </div>
            {stats.focus === null && (
              <div style={styles.emptyMessage}>Complete sessions to see your score</div>
            )}
          </div>
          <div 
            style={{
              ...styles.statCard, 
              transform: hoveredStat === 'streak' ? 'translateY(-4px)' : 'translateY(0)',
              borderColor: hoveredStat === 'streak' ? 'rgba(59,130,246,0.5)' : 'rgba(59,130,246,0.2)',
            }}
            onMouseEnter={() => setHoveredStat('streak')}
            onMouseLeave={() => setHoveredStat(null)}
          >
            <div style={styles.statLabel}>🔥 Learning Streak</div>
            <div style={styles.statValue}>{stats.streak}</div>
            {stats.streak === 0 && (
              <div style={styles.emptyMessage}>Learn daily to build your streak</div>
            )}
          </div>
        </div>

        {/* Key Metrics */}
        {lastSessionSummary && (
          <div style={{...styles.metricsSection, background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(6, 182, 212, 0.1) 100%)', border: '2px solid #22c55e', borderRadius: '16px', padding: '24px', marginBottom: '30px', boxShadow: '0 12px 40px rgba(34, 197, 94, 0.15)'}}>
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px'}}>
              <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
                <span style={{fontSize: '32px'}}>🎉</span>
                <div>
                  <h2 style={{margin: '0', color: '#22c55e', fontSize: '22px'}}>Session Complete!</h2>
                  <p style={{margin: '4px 0 0 0', color: '#94a3b8', fontSize: '14px'}}>Great job! Here's your session summary.</p>
                </div>
              </div>
              <button 
                onClick={() => setLastSessionSummary(null)}
                style={{background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#94a3b8'}}
                title="Dismiss"
              >
                ✕
              </button>
            </div>

            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '14px', marginBottom: '20px'}}>
              <div style={{backgroundColor: 'rgba(15, 23, 42, 0.6)', padding: '14px', borderRadius: '10px', textAlign: 'center', border: '1px solid rgba(59, 130, 246, 0.2)'}}>
                <div style={{fontSize: '12px', color: '#94a3b8', marginBottom: '6px', fontWeight: '600'}}>📚 Topic</div>
                <div style={{fontSize: '14px', fontWeight: 'bold', color: '#22c55e'}}>{lastSessionSummary.topic}</div>
              </div>
              <div style={{backgroundColor: 'rgba(15, 23, 42, 0.6)', padding: '14px', borderRadius: '10px', textAlign: 'center', border: '1px solid rgba(59, 130, 246, 0.2)'}}>
                <div style={{fontSize: '12px', color: '#94a3b8', marginBottom: '6px', fontWeight: '600'}}>⏱️ Duration</div>
                <div style={{fontSize: '14px', fontWeight: 'bold', color: '#06b6d4'}}>{lastSessionSummary.duration}</div>
              </div>
              <div style={{backgroundColor: 'rgba(15, 23, 42, 0.6)', padding: '14px', borderRadius: '10px', textAlign: 'center', border: '1px solid rgba(59, 130, 246, 0.2)'}}>
                <div style={{fontSize: '12px', color: '#94a3b8', marginBottom: '6px', fontWeight: '600'}}>💬 Steps</div>
                <div style={{fontSize: '14px', fontWeight: 'bold', color: '#3b82f6'}}>{lastSessionSummary.stepCount}</div>
              </div>
              <div style={{backgroundColor: 'rgba(15, 23, 42, 0.6)', padding: '14px', borderRadius: '10px', textAlign: 'center', border: '1px solid rgba(59, 130, 246, 0.2)'}}>
                <div style={{fontSize: '12px', color: '#94a3b8', marginBottom: '6px', fontWeight: '600'}}>🎯 Engagement</div>
                <div style={{fontSize: '14px', fontWeight: 'bold', color: '#22c55e'}}>{Math.round((lastSessionSummary.emotionJourney.engaged / (lastSessionSummary.assistantMessagesExchanged || lastSessionSummary.messagesExchanged || 1)) * 100)}%</div>
              </div>
            </div>

            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '10px'}}>
              <button 
                onClick={() => navigate('/history', { state: { resumeSessionId: lastSessionSummary.sessionId } })}
                style={{padding: '10px 16px', backgroundColor: '#22c55e', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', transition: 'all 0.3s'}}
                onMouseEnter={(e) => e.target.style.opacity = '0.9'}
                onMouseLeave={(e) => e.target.style.opacity = '1'}
              >
                ⏱️ Resume
              </button>
              <button 
                onClick={downloadSessionSummaryAsPDF}
                style={{padding: '10px 16px', backgroundColor: '#f59e0b', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', transition: 'all 0.3s'}}
                onMouseEnter={(e) => e.target.style.opacity = '0.9'}
                onMouseLeave={(e) => e.target.style.opacity = '1'}
              >
                📄 Summary PDF
              </button>
              <button 
                onClick={() => navigate('/history')}
                style={{padding: '10px 16px', backgroundColor: '#3b82f6', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', transition: 'all 0.3s'}}
                onMouseEnter={(e) => e.target.style.opacity = '0.9'}
                onMouseLeave={(e) => e.target.style.opacity = '1'}
              >
                📜 History
              </button>
              <button 
                onClick={() => setLastSessionSummary(null)}
                style={{padding: '10px 16px', backgroundColor: '#64748b', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', transition: 'all 0.3s'}}
                onMouseEnter={(e) => e.target.style.opacity = '0.9'}
                onMouseLeave={(e) => e.target.style.opacity = '1'}
              >
                ✓ Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Action Cards */}
        <div style={styles.actionsLabel}>Quick Access</div>
        <div style={styles.actionsGrid}>
          <div 
            style={{
              ...styles.actionCard,
              transform: hoveredCard === 'learning' ? 'translateY(-8px)' : 'translateY(0)',
              boxShadow: hoveredCard === 'learning' 
                ? '0 20px 40px rgba(59,130,246,0.5)' 
                : '0 10px 30px rgba(59,130,246,0.3)',
            }}
            onClick={() => navigate('/learning')}
            onMouseEnter={() => setHoveredCard('learning')}
            onMouseLeave={() => setHoveredCard(null)}
          >
            <div style={styles.actionIcon}>�</div>
            <div style={styles.actionTitle}>Start Learning</div>
            <div style={styles.actionDesc}>Practice emotion detection</div>
          </div>

          <div 
            style={{
              ...styles.actionCard,
              transform: hoveredCard === 'history' ? 'translateY(-8px)' : 'translateY(0)',
              boxShadow: hoveredCard === 'history' 
                ? '0 20px 40px rgba(59,130,246,0.5)' 
                : '0 10px 30px rgba(59,130,246,0.3)',
            }}
            onClick={() => navigate('/history')}
            onMouseEnter={() => setHoveredCard('history')}
            onMouseLeave={() => setHoveredCard(null)}
          >
            <div style={styles.actionIcon}>�</div>
            <div style={styles.actionTitle}>Session History</div>
            <div style={styles.actionDesc}>View and resume past learning</div>
          </div>

          <div 
            style={{
              ...styles.actionCard,
              transform: hoveredCard === 'analytics' ? 'translateY(-8px)' : 'translateY(0)',
              boxShadow: hoveredCard === 'analytics' 
                ? '0 20px 40px rgba(59,130,246,0.5)' 
                : '0 10px 30px rgba(59,130,246,0.3)',
            }}
            onClick={() => navigate('/analytics')}
            onMouseEnter={() => setHoveredCard('analytics')}
            onMouseLeave={() => setHoveredCard(null)}
          >
            <div style={styles.actionIcon}>📊</div>
            <div style={styles.actionTitle}>View Analytics</div>
            <div style={styles.actionDesc}>Track your progress</div>
          </div>

          <div 
            style={{
              ...styles.actionCard,
              transform: hoveredCard === 'friend-chat' ? 'translateY(-8px)' : 'translateY(0)',
              boxShadow: hoveredCard === 'friend-chat' 
                ? '0 20px 40px rgba(59,130,246,0.5)' 
                : '0 10px 30px rgba(59,130,246,0.3)',
            }}
            onClick={() => navigate('/friend-chat')}
            onMouseEnter={() => setHoveredCard('friend-chat')}
            onMouseLeave={() => setHoveredCard(null)}
          >
            <div style={styles.actionIcon}>�</div>
            <div style={styles.actionTitle}>Friend Chat</div>
            <div style={styles.actionDesc}>Realtime translated chat</div>
          </div>
        </div>

        {/* Smart Message */}
        {data && data.confused > 50 && (
          <p style={styles.smartMessage}>
            🤔 You're struggling. Try simpler explanations or take a break.
          </p>
        )}
        {data && data.engaged > data.frustrated && (
          <p style={styles.smartMessage}>
            🎉 You're doing great! Keep this momentum going.
          </p>
        )}
      </div>
    </div>
  )
}

const getStyles = (theme, fontSize) => {
  const fs = parseInt(fontSize) || 16
  const isDark = theme === 'dark'
  
  return {
    container: {
      minHeight: '100vh',
      width: '100%',
      background: '#0b1220',
      color: 'white',
      fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      fontSize: `${fs}px`,
      lineHeight: 1.58,
      letterSpacing: '0.01em',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-start',
      padding: '16px 16px 14px',
    },
    main: {
      width: '100%',
      maxWidth: '1080px',
      margin: '0 auto',
      background: '#0f172a',
      borderRadius: '20px',
      padding: '28px 32px',
      boxShadow: '0 20px 50px rgba(0,0,0,0.22)',
      display: 'flex',
      flexDirection: 'column',
      gap: '24px',
      overflow: 'visible',
    },
    header: {
      marginBottom: '0',
    },
    headerTop: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      gap: '20px',
      flexWrap: 'wrap',
    },
    headerLeft: {
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      flex: '1 1 320px',
      minWidth: '240px',
    },
    headerRight: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      gap: '18px',
      alignItems: 'flex-end',
      minWidth: '240px',
    },
    avatarButton: {
      width: '46px',
      height: '46px',
      borderRadius: '50%',
      background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
      border: '1px solid rgba(255,255,255,0.18)',
      color: 'white',
      display: 'grid',
      placeItems: 'center',
      cursor: 'pointer',
      boxShadow: '0 16px 40px rgba(0,0,0,0.2)',
      fontSize: '16px',
      fontWeight: '800',
      transition: 'transform 0.2s ease, box-shadow 0.2s ease',
    },
    avatarInitial: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '100%',
      height: '100%',
      borderRadius: '50%',
    },
    profileCard: {
      width: '100%',
      maxWidth: '300px',
      background: 'rgba(15, 23, 42, 0.98)',
      border: '1px solid rgba(148, 163, 184, 0.14)',
      borderRadius: '18px',
      padding: '18px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      boxShadow: '0 14px 36px rgba(0,0,0,0.18)',
      position: 'absolute',
      right: '0',
      top: '68px',
      zIndex: 20,
    },
    profileTitle: {
      margin: 0,
      color: '#cbd5e1',
      fontSize: `${Math.round(fs * 0.95)}px`,
      fontWeight: '700',
      letterSpacing: '0.4px',
    },
    profileMeta: {
      display: 'flex',
      justifyContent: 'space-between',
      gap: '10px',
      alignItems: 'center',
      fontSize: `${Math.round(fs * 0.9)}px`,
      color: '#94a3b8',
    },
    profileLabel: {
      color: '#94a3b8',
      fontWeight: '600',
    },
    profileValue: {
      color: '#ffffff',
      fontWeight: '600',
      textAlign: 'right',
    },
    profileButton: {
      marginTop: '10px',
      padding: '10px 14px',
      borderRadius: '12px',
      border: '1px solid rgba(59, 130, 246, 0.28)',
      background: 'rgba(59, 130, 246, 0.16)',
      color: '#ffffff',
      fontWeight: '700',
      cursor: 'pointer',
      transition: 'all 0.25s ease',
      alignSelf: 'stretch',
      fontSize: '13px',
    },
    accessibilityBtn: {
      fontSize: '18px',
      padding: '8px 12px',
      background: isDark ? 'rgba(59,130,246,0.15)' : 'rgba(59,130,246,0.12)',
      border: `1px solid ${isDark ? 'rgba(59,130,246,0.25)' : 'rgba(59,130,246,0.2)'}`,
      borderRadius: '12px',
      cursor: 'pointer',
      transition: 'all 0.3s ease',
      color: isDark ? 'white' : '#1e293b',
    },
    fontsizeSelect: {
      padding: '10px 14px',
      background: isDark ? 'rgba(59,130,246,0.12)' : 'rgba(59,130,246,0.08)',
      border: `1px solid ${isDark ? 'rgba(59,130,246,0.25)' : 'rgba(59,130,246,0.25)'}`,
      borderRadius: '12px',
      color: isDark ? '#cbd5e1' : '#1e293b',
      fontSize: `${Math.round(fs * 0.88)}px`,
      cursor: 'pointer',
      transition: 'all 0.3s ease',
    },
    title: {
      margin: '0 0 12px 0',
      fontSize: `${Math.round(fs * 2.4)}px`,
      fontWeight: '800',
      color: '#ffffff',
      letterSpacing: '0.2px',
    },
    subtitle: {
      margin: '0',
      color: '#94a3b8',
      fontSize: `${Math.round(fs * 1)}px`,
      fontWeight: '400',
      letterSpacing: '0.3px',
    },
    statsGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '16px',
      marginBottom: '0',
    },
    statCard: {
      background: 'rgba(15, 23, 42, 0.96)',
      padding: '20px 18px',
      borderRadius: '18px',
      border: '1px solid rgba(148, 163, 184, 0.10)',
      textAlign: 'center',
      transition: 'transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease',
      boxShadow: '0 10px 28px rgba(0,0,0,0.16)',
      cursor: 'default',
      color: 'white',
    },
    statLabel: {
      fontSize: `${Math.round(fs * 0.85)}px`,
      color: '#94a3b8',
      marginBottom: '12px',
      fontWeight: '600',
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
    },
    statValue: {
      fontSize: `${Math.round(fs * 2)}px`,
      fontWeight: '800',
      color: '#60a5fa',
    },
    emptyMessage: {
      fontSize: `${Math.round(fs * 0.75)}px`,
      color: '#64748b',
      marginTop: '10px',
      fontStyle: 'italic',
      lineHeight: '1.4',
    },
    metricsSection: {
      marginBottom: '50px',
      marginTop: '40px',
      padding: '26px',
      borderRadius: '22px',
      background: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(102, 126, 234, 0.12)',
    },
    sectionTitle: {
      fontSize: `${Math.round(fs * 1.1)}px`,
      fontWeight: '700',
      marginBottom: '20px',
      color: 'white',
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
      margin: '0 0 20px 0',
    },
    metricsGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
      gap: '15px',
    },
    metricBox: {
      background: 'rgba(15, 23, 42, 0.92)',
      padding: '18px 16px',
      borderRadius: '14px',
      border: '1px solid rgba(148, 163, 184, 0.12)',
      textAlign: 'center',
      transition: 'all 0.3s ease',
      cursor: 'default',
      color: 'white',
    },
    metricLabel: {
      fontSize: `${Math.round(fs * 0.75)}px`,
      color: '#94a3b8',
      marginBottom: '8px',
      fontWeight: '600',
      textTransform: 'uppercase',
      letterSpacing: '0.4px',
    },
    metricValue: {
      fontSize: `${Math.round(fs * 1.5)}px`,
      fontWeight: '700',
      color: '#60a5fa',
    },
    actionsLabel: {
      fontSize: `${Math.round(fs * 1.1)}px`,
      fontWeight: '700',
      marginBottom: '20px',
      color: 'white',
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
    },
    actionsGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
      gap: '16px',
      marginBottom: '30px',
    },
    actionCard: {
      background: 'rgba(15, 23, 42, 0.94)',
      padding: '22px 18px',
      borderRadius: '18px',
      border: '1px solid rgba(148, 163, 184, 0.10)',
      textAlign: 'center',
      cursor: 'pointer',
      transition: 'transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease',
      boxShadow: '0 10px 30px rgba(0,0,0,0.16)',
      minHeight: '170px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      gap: '10px',
    },
    actionIcon: {
      fontSize: '36px',
      marginBottom: '12px',
    },
    actionTitle: {
      fontSize: `${Math.round(fs * 1.05)}px`,
      fontWeight: '700',
      marginBottom: '6px',
      color: 'white',
    },
    actionDesc: {
      fontSize: `${Math.round(fs * 0.9)}px`,
      color: '#94a3b8',
      lineHeight: '1.4',
    },
    smartMessage: {
      fontSize: `${Math.round(fs * 0.95)}px`,
      padding: '14px 16px',
      borderRadius: '16px',
      background: 'rgba(15, 23, 42, 0.94)',
      border: '1px solid rgba(148, 163, 184, 0.10)',
      color: '#cbd5e1',
      marginTop: '16px',
    },
  }
}

export default Dashboard
