import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend, PieChart, Pie } from 'recharts'

function Analytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generatingReport, setGeneratingReport] = useState(false)

  useEffect(() => {
    const userId = localStorage.getItem('user_id')
    fetch(`/api/learning/analytics?user_id=${userId}`)
      .then(res => res.json())
      .then(data => {
        setData(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const generateReport = () => {
    setGeneratingReport(true)
    setTimeout(() => {
      const topTopics = data.topic_mastery 
        ? data.topic_mastery.slice(0, 3).map((t, i) => `${i + 1}. ${t.topic} (${t.mastery}% mastery)`).join('\n')
        : `${data.concepts_mastered || 0} Concepts Mastered`
        
      const report = `
🎓 AI LEARNING SUMMARY REPORT

📊 Overall Progress:
• Total Sessions: ${data.total_sessions || 0}
• Concepts Mastered: ${data.concepts_mastered || 0}
• Engagement Score: ${data.engagement_score || 0}%

🎯 Top Strengths:
${topTopics || 'No topics completed yet'}

💡 Personalized Insights:
${data.ai_insights || 'Keep practicing to get more personalized insights from your AI tutor!'}

Keep learning! 🚀
      `
      alert(report)
      setGeneratingReport(false)
    }, 500)
  }

  if (loading) return <div style={styles.container}><p style={{ color: '#94a3b8' }}>Loading your analytics...</p></div>
  if (error) return <div style={styles.container}><p style={{ color: '#ef4444' }}>Error: {error}</p></div>
  if (!data || data.total_sessions === 0) return (
    <div style={styles.container}>
      <div style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>📊 Learning Dashboard</h1>
          <p style={styles.subtitle}>Start your first learning session to see analytics</p>
        </div>
      </div>
    </div>
  )

  // Map to the new backend schema if old is missing
  const emotionChartData = [
    { name: 'Correct Answers', value: Math.max(data.answers_correct || 0, 0), color: '#10b981' },
    { name: 'Examples Req', value: Math.max(data.examples_requested || 0, 0), color: '#2563eb' },
    { name: 'Confusion', value: Math.max(data.confusion_spikes || 0, 0), color: '#f59e0b' },
  ]
  // Add fallback if it's the old schema
  if (data.emotion_distribution) {
    emotionChartData[0] = { name: 'Engaged', value: Math.max(data.emotion_distribution.engaged || 0, 0), color: '#10b981' }
    emotionChartData[1] = { name: 'Neutral', value: Math.max(data.emotion_distribution.neutral || 0, 0), color: '#64748b' }
    emotionChartData[2] = { name: 'Confused', value: Math.max(data.emotion_distribution.confused || 0, 0), color: '#f59e0b' }
  }

  const topicMastery = data.topic_mastery || []
  
  // Try to use study_activity, else map learning_dates if available
  let studyActivityArray = []
  if (data.study_activity) {
    studyActivityArray = Object.entries(data.study_activity)
      .map(([date, minutes]) => {
        const parsedDate = new Date(date)
        const label = parsedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        return {
          date,
          day: label,
          minutes: parseInt(minutes) || 0
        }
      })
      .sort((a, b) => new Date(a.date) - new Date(b.date))
      .slice(-7)
  } else if (data.learning_dates && data.learning_dates.length > 0) {
    // Distribute total_active_minutes across learning dates as a rough approximation
    const minsPerDay = Math.round((data.total_active_minutes || 0) / data.learning_dates.length) || 15
    studyActivityArray = data.learning_dates.map(date => {
        const parsedDate = new Date(date)
        const label = parsedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        return {
            date,
            day: label,
            minutes: minsPerDay
        }
    }).slice(-7)
  }

  const aiInsights = data.ai_insights || (data.engagement_score > 50 
    ? "You're showing great engagement! Keep asking for examples when needed. Your event logs show solid progression." 
    : "Complete more sessions to unlock personalized insights!");

  const formatTime = (minutes) => {
    if (!minutes || minutes === 0) return '0h'
    const roundedMins = Math.round(minutes)
    const hours = Math.floor(roundedMins / 60)
    const mins = roundedMins % 60
    
    if (hours === 0) return `${mins}m`
    if (mins === 0) return `${hours}h`
    return `${hours}h ${mins}m`
  }

  return (
    <div style={styles.container}>
      <div style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>📊 Learning Intelligence Dashboard</h1>
          <p style={styles.subtitle}>AI-powered insights into your learning journey</p>
          <button
            onClick={generateReport}
            disabled={generatingReport}
            style={{
              ...styles.reportButton,
              opacity: generatingReport ? 0.6 : 1,
              cursor: generatingReport ? 'not-allowed' : 'pointer'
            }}
          >
            {generatingReport ? '⏳ Generating...' : '📋 Generate AI Report'}
          </button>
        </div>

        <div style={styles.gridRow}>
          <div style={{ ...styles.card, gridColumn: '1 / 2' }}>
            <h2 style={styles.sectionTitle}>🎯 Interaction Breakdown</h2>
            {emotionChartData.some(e => e.value > 0) ? (
              <div style={styles.chartContainer}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={emotionChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {emotionChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `${value}`} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={styles.emotionLegend}>
                  {emotionChartData.map((e, i) => (
                    <div key={i} style={styles.legendItem}>
                      <div style={{ ...styles.legendDot, backgroundColor: e.color }}></div>
                      <span>{e.name}: {e.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p style={{ color: '#94a3b8', textAlign: 'center', padding: '30px' }}>No interaction data available</p>
            )}
          </div>

          <div style={{ ...styles.card, gridColumn: '2 / 3' }}>
            <h2 style={styles.sectionTitle}>🏆 Mastery & Streak</h2>
            <div style={styles.masteryContainer}>
                {topicMastery && topicMastery.length > 0 ? (
                  <div style={styles.topicsList}>
                    {topicMastery.map((topic, idx) => (
                      <div key={idx} style={styles.topicItem}>
                        <div style={styles.topicName}>{topic.topic}</div>
                        <div style={styles.topicBarContainer}>
                          <div
                            style={{
                              ...styles.topicBar,
                              width: `${topic.mastery}%`,
                              backgroundColor: getMasteryColor(topic.mastery)
                            }}
                          ></div>
                        </div>
                        <div style={styles.topicPercent}>{topic.mastery}%</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={styles.streakBox}>
                    <div style={styles.streakItem}>
                      <span style={styles.streakLabel}>Concepts Mastered</span>
                      <span style={styles.streakValue}>{data.concepts_mastered || 0}</span>
                    </div>
                    <div style={styles.streakItem}>
                      <span style={styles.streakLabel}>Answers Attempted</span>
                      <span style={styles.streakValue}>{data.answers_attempted || 0}</span>
                    </div>
                    <div style={styles.streakItem}>
                      <span style={styles.streakLabel}>Eligible For Streak</span>
                      <span style={styles.streakValue}>{data.ready_for_streak ? '🔥 Yes' : '⏳ Keep going'}</span>
                    </div>
                  </div>
                )}
            </div>
          </div>
        </div>

        {/* SECTION 4: Study Activity */}
        <div style={styles.gridRow}>
          <div style={{ ...styles.card, gridColumn: '1 / -1' }}>
            <h2 style={styles.sectionTitle}>📅 Study Activity (Minutes)</h2>
            {studyActivityArray.length > 0 && studyActivityArray.some(a => a.minutes > 0) ? (
              <div style={styles.chartContainer}>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={studyActivityArray} margin={{ top: 10, right: 30, left: 0, bottom: 10 }}>
                    <XAxis dataKey="day" stroke="#64748b" style={{ fontSize: '12px' }} />
                    <YAxis stroke="#64748b" label={{ value: 'Minutes', angle: -90, position: 'insideLeft' }} />
                    <Tooltip
                      contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                      labelStyle={{ color: '#e2e8f0' }}
                      formatter={(value) => `${value} min`}
                      cursor={{ fill: 'rgba(37,99,235,0.1)' }}
                    />
                    <Bar dataKey="minutes" fill="#06b6d4" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p style={{ color: '#94a3b8', textAlign: 'center', padding: '30px' }}>No study activity yet</p>
            )}
          </div>
        </div>

        {/* SECTION 5: AI Insights */}
        <div style={styles.gridRow}>
          <div style={{ ...styles.card, gridColumn: '1 / -1', background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(16, 185, 129, 0.1))' }}>
            <h2 style={styles.sectionTitle}>🧠 AI Learning Insights</h2>
            <div style={styles.insightsText}>
              {aiInsights ? (
                aiInsights.split('\n\n').map((insight, idx) => (
                  <p key={idx} style={styles.insightParagraph}>{insight}</p>
                ))
              ) : (
                <p style={styles.insightParagraph}>Keep learning to unlock personalized insights!</p>
              )}
            </div>
          </div>
        </div>

        {/* SECTION 6: Quick Stats */}
        <div style={styles.gridRow}>
          <div style={{ ...styles.card, gridColumn: '1 / -1' }}>
            <div style={styles.statsGrid}>
              <div style={styles.statBox}>
                <div style={styles.statNumber}>{data.total_sessions}</div>
                <div style={styles.statLabel}>Sessions</div>
              </div>
              <div style={styles.statBox}>
                <div style={styles.statNumber}>{data.meaningful_events || topicMastery.length || 0}</div>
                <div style={styles.statLabel}>Meaningful Events</div>
              </div>
              <div style={styles.statBox}>
                <div style={styles.statNumber}>{data.engagement_score ? data.engagement_score + '%' : (data.engaged || 0)}</div>
                <div style={styles.statLabel}>Engagement</div>
              </div>
              <div style={styles.statBox}>
                <div style={styles.statNumber}>{formatTime(data.total_active_minutes || data.total_time) || '0h'}</div>
                <div style={styles.statLabel}>Active Time</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function getMasteryColor(mastery) {
  if (mastery >= 80) return '#10b981'
  if (mastery >= 60) return '#2563eb'
  if (mastery >= 40) return '#f59e0b'
  return '#ef4444'
}

const styles = {
  container: {
    minHeight: '100vh',
    background: 'rgba(11,18,32,1)',
    color: 'white',
    padding: '40px 20px',
  },
  main: {
    width: '100%',
    maxWidth: '1200px',
    margin: '0 auto',
  },
  header: {
    marginBottom: '40px',
    textAlign: 'center',
  },
  title: {
    margin: '0 0 12px 0',
    fontSize: '42px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
    letterSpacing: '-0.5px',
  },
  subtitle: {
    margin: '0 0 20px 0',
    fontSize: '16px',
    color: '#94a3b8',
    fontWeight: '500',
  },
  reportButton: {
    background: 'rgba(37,99,235,0.12)',
    border: '1px solid rgba(37,99,235,0.12)',
    color: 'white',
    padding: '10px 20px',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.25s ease',
    boxShadow: '0 6px 18px rgba(2,6,23,0.06)',
  },
  gridRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
    marginBottom: '20px',
  },
  card: {
    background: 'rgba(15,23,42,0.9)',
    padding: '22px',
    borderRadius: '12px',
    border: '1px solid rgba(148,163,184,0.06)',
    boxShadow: '0 8px 24px rgba(2,6,23,0.08)',
  },
  sectionTitle: {
    margin: '0 0 20px 0',
    fontSize: '18px',
    fontWeight: '700',
    color: '#e2e8f0',
    letterSpacing: '0.3px',
  },
  chartContainer: {
    background: 'rgba(15, 23, 42, 0.74)',
    padding: '18px',
    borderRadius: '8px',
    border: '1px solid rgba(148,163,184,0.06)',
  },
  masteryContainer: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    height: '100%',
    minHeight: '200px',
  },
  streakBox: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    padding: '10px',
  },
  streakItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: 'rgba(37,99,235,0.08)',
    padding: '16px',
    borderRadius: '8px',
    border: '1px solid rgba(37,99,235,0.2)',
  },
  streakLabel: {
    fontSize: '15px',
    color: '#cbd5e1',
    fontWeight: '600',
  },
  streakValue: {
    fontSize: '18px',
    color: '#38bdf8',
    fontWeight: '800',
  },
  topicsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  topicItem: {
    display: 'grid',
    gridTemplateColumns: '1fr 2fr 0.5fr',
    alignItems: 'center',
    gap: '12px',
  },
  topicName: {
    fontSize: '13px',
    color: '#cbd5e1',
    fontWeight: '600',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  topicBarContainer: {
    background: 'rgba(71, 85, 105, 0.3)',
    borderRadius: '4px',
    height: '8px',
    overflow: 'hidden',
  },
  topicBar: {
    height: '100%',
    borderRadius: '4px',
    transition: 'width 0.3s',
  },
  topicPercent: {
    fontSize: '13px',
    color: '#94a3b8',
    fontWeight: '600',
    textAlign: 'right',
  },
  emotionLegend: {
    display: 'flex',
    justifyContent: 'center',
    gap: '24px',
    marginTop: '16px',
    flexWrap: 'wrap',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    color: '#cbd5e1',
  },
  legendDot: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
  },
  insightsText: {
    lineHeight: '1.8',
    color: '#cbd5e1',
  },
  insightParagraph: {
    margin: '12px 0',
    fontSize: '14px',
    lineHeight: '1.6',
    color: '#e2e8f0',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '16px',
  },
  statBox: {
    background: 'rgba(148,163,184,0.02)',
    padding: '18px',
    borderRadius: '8px',
    textAlign: 'center',
    border: '1px solid rgba(148,163,184,0.06)',
  },
  statNumber: {
    fontSize: '28px',
    fontWeight: '800',
    color: '#2563eb',
    marginBottom: '8px',
  },
  statLabel: {
    fontSize: '12px',
    color: '#94a3b8',
    fontWeight: '600',
    textTransform: 'uppercase',
  },
}

export default Analytics

