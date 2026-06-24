import React, { useState, useEffect } from 'react'
import { colors, borderRadius } from '../config/theme'

/**
 * Analytics Dashboard Component
 * 
 * Displays:
 * - Live learning stats (streak, accuracy, concepts mastered)
 * - Emotion distribution
 * - Response effectiveness
 * - Drop-off points
 * - AI adaptation indicators
 */
const AnalyticsDashboard = ({ sessionId }) => {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  // Fetch dashboard metrics
  useEffect(() => {
    if (!sessionId) return

    const fetchMetrics = async () => {
      try {
        setLoading(true)
        const response = await fetch(`/api/analytics/dashboard/${sessionId}`)
        const data = await response.json()
        
        if (data.success) {
          setMetrics(data.metrics)
          setError(null)
        } else {
          setError('Failed to load analytics')
        }
      } catch (err) {
        console.error('Error fetching analytics:', err)
        setError('Could not connect to analytics service')
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
    
    // Refresh every 10 seconds for live updates
    const interval = setInterval(fetchMetrics, 10000)
    return () => clearInterval(interval)
  }, [sessionId])

  const refresh = async () => {
    setRefreshing(true)
    try {
      const response = await fetch(`/api/analytics/dashboard/${sessionId}`)
      const data = await response.json()
      if (data.success) {
        setMetrics(data.metrics)
      }
    } catch (err) {
      console.error('Error refreshing:', err)
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <div style={{
        padding: '20px',
        textAlign: 'center',
        color: colors.text,
        fontSize: '14px'
      }}>
        📊 Loading analytics...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        padding: '20px',
        textAlign: 'center',
        color: '#ef4444',
        fontSize: '14px'
      }}>
        ⚠️ {error}
      </div>
    )
  }

  if (!metrics) {
    return null
  }

  // Get dominant emotion
  const emotionDist = metrics.emotion_distribution || {}
  const dominantEmotion = Object.keys(emotionDist).length > 0
    ? Object.entries(emotionDist).sort(([,a], [,b]) => b - a)[0][0]
    : 'neutral'

  // Get emoji for emotion
  const emotionEmoji = {
    'very_frustrated': '😡',
    'frustrated': '😠',
    'confused': '😕',
    'neutral': '😐',
    'engaged': '😊',
    'very_engaged': '🤩'
  }[dominantEmotion] || '😐'

  return (
    <div style={{
      backgroundColor: colors.background,
      borderRadius: borderRadius,
      padding: '20px',
      marginBottom: '20px',
      border: `1px solid ${colors.border}`
    }}>
      {/* Header with refresh button */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
        borderBottom: `1px solid ${colors.border}`,
        paddingBottom: '15px'
      }}>
        <h2 style={{ margin: 0, color: colors.text, fontSize: '18px', fontWeight: 'bold' }}>
          📊 Live Learning Analytics
        </h2>
        <button
          onClick={refresh}
          disabled={refreshing}
          style={{
            padding: '8px 12px',
            backgroundColor: refreshing ? '#9ca3af' : colors.accent,
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: refreshing ? 'default' : 'pointer',
            fontSize: '12px',
            fontWeight: '600',
            opacity: refreshing ? 0.7 : 1
          }}
        >
          {refreshing ? '⟳ Updating...' : '🔄 Refresh'}
        </button>
      </div>

      {/* Live Stats Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '15px',
        marginBottom: '25px'
      }}>
        {/* Streak */}
        <div style={{
          backgroundColor: 'rgba(236, 72, 153, 0.1)',
          padding: '15px',
          borderRadius: '8px',
          borderLeft: '4px solid #ec4899',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#ec4899' }}>
            🔥 {metrics.streak}
          </div>
          <div style={{ fontSize: '12px', color: colors.text, marginTop: '5px' }}>
            Current Streak
          </div>
        </div>

        {/* Accuracy */}
        <div style={{
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          padding: '15px',
          borderRadius: '8px',
          borderLeft: '4px solid #22c55e',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#22c55e' }}>
            📈 {metrics.accuracy}%
          </div>
          <div style={{ fontSize: '12px', color: colors.text, marginTop: '5px' }}>
            Response Accuracy
          </div>
        </div>

        {/* Concepts Mastered */}
        <div style={{
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          padding: '15px',
          borderRadius: '8px',
          borderLeft: '4px solid #3b82f6',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#3b82f6' }}>
            🧠 {metrics.concepts_mastered || 0}
          </div>
          <div style={{ fontSize: '12px', color: colors.text, marginTop: '5px' }}>
            Concepts Mastered
          </div>
        </div>

        {/* Current Mood */}
        <div style={{
          backgroundColor: 'rgba(168, 85, 247, 0.1)',
          padding: '15px',
          borderRadius: '8px',
          borderLeft: '4px solid #a855f7',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '28px', fontWeight: 'bold' }}>
            {emotionEmoji} {dominantEmotion}
          </div>
          <div style={{ fontSize: '12px', color: colors.text, marginTop: '5px' }}>
            Current Emotion
          </div>
        </div>
      </div>

      {/* Emotion Distribution */}
      {Object.keys(emotionDist).length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ color: colors.text, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
            😊 Emotion Distribution
          </h3>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {Object.entries(emotionDist).map(([emotion, percentage]) => (
              <div
                key={emotion}
                style={{
                  flex: `0 1 ${percentage}%`,
                  minWidth: '30px',
                  backgroundColor: {
                    'very_frustrated': '#dc2626',
                    'frustrated': '#f97316',
                    'confused': '#eab308',
                    'neutral': '#6b7280',
                    'engaged': '#22c55e',
                    'very_engaged': '#3b82f6'
                  }[emotion] || '#9ca3af',
                  padding: '8px',
                  borderRadius: '4px',
                  textAlign: 'center',
                  color: '#fff',
                  fontSize: '11px',
                  fontWeight: 'bold',
                  minHeight: '30px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                title={`${emotion}: ${percentage}%`}
              >
                {percentage > 15 ? `${percentage}%` : ''}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Response Effectiveness */}
      <div style={{ marginBottom: '20px' }}>
        <h3 style={{ color: colors.text, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
          ⭐ Response Effectiveness
        </h3>
        <div style={{
          backgroundColor: colors.background,
          padding: '15px',
          borderRadius: '8px',
          border: `1px solid ${colors.border}`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              fontSize: '28px',
              fontWeight: 'bold',
              color: metrics.response_effectiveness > 70 ? '#22c55e' : 
                     metrics.response_effectiveness > 50 ? '#f97316' : '#dc2626'
            }}>
              {metrics.response_effectiveness}%
            </div>
            <div style={{ flex: 1 }}>
              <div style={{
                height: '8px',
                backgroundColor: '#e5e7eb',
                borderRadius: '4px',
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${metrics.response_effectiveness}%`,
                  backgroundColor: metrics.response_effectiveness > 70 ? '#22c55e' : 
                                   metrics.response_effectiveness > 50 ? '#f97316' : '#dc2626',
                  transition: 'width 0.3s ease'
                }} />
              </div>
              <div style={{ fontSize: '11px', color: colors.text, marginTop: '5px' }}>
                {metrics.total_feedback || 0} responses rated
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Drop-off Points */}
      {metrics.drop_off_points && metrics.drop_off_points.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ color: '#dc2626', fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
            ⚠️ Drop-off Points (Topics Causing Confusion)
          </h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {metrics.drop_off_points.map((topic) => (
              <div
                key={topic}
                style={{
                  backgroundColor: 'rgba(220, 38, 38, 0.1)',
                  color: '#dc2626',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: '600',
                  border: '1px solid rgba(220, 38, 38, 0.3)'
                }}
              >
                {topic}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* High Confusion Topics */}
      {metrics.high_confusion_topics && metrics.high_confusion_topics.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ color: colors.text, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
            🧠 Topics Needing Attention
          </h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {metrics.high_confusion_topics.map((topic) => (
              <div
                key={topic}
                style={{
                  backgroundColor: 'rgba(249, 115, 22, 0.1)',
                  color: '#f97316',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: '600',
                  border: '1px solid rgba(249, 115, 22, 0.3)'
                }}
              >
                {topic}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Concepts Covered */}
      {metrics.concepts_covered && metrics.concepts_covered.length > 0 && (
        <div>
          <h3 style={{ color: colors.text, fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
            ✅ Concepts Covered
          </h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {metrics.concepts_covered.map((concept) => (
              <div
                key={concept}
                style={{
                  backgroundColor: 'rgba(34, 197, 94, 0.1)',
                  color: '#22c55e',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: '600',
                  border: '1px solid rgba(34, 197, 94, 0.3)'
                }}
              >
                {concept}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info message */}
      <div style={{
        marginTop: '20px',
        padding: '12px',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderRadius: '6px',
        fontSize: '12px',
        color: '#3b82f6',
        borderLeft: '3px solid #3b82f6'
      }}>
        💡 <strong>Tip:</strong> Rate responses with 👍/👎 to improve these analytics and help the system learn!
      </div>
    </div>
  )
}

export default AnalyticsDashboard
