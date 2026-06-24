import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import SessionQuiz from '../components/SessionQuiz'

function Learning() {
  const [topic, setTopic] = useState('')
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [elapsedTime, setElapsedTime] = useState(0)
  const [accumulatedTime, setAccumulatedTime] = useState(0)
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState([])
  const [emotion, setEmotion] = useState('neutral')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const theme = 'dark'
  const [fontSize, setFontSize] = useState(() => parseInt(localStorage.getItem('echoFontSize')) || 13)
  const [textToSpeechEnabled, setTextToSpeechEnabled] = useState(() => localStorage.getItem('echoTTS') !== 'false') // Default: ENABLED
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [stepCount, setStepCount] = useState(0)
  const [userReactions, setUserReactions] = useState({})
  const [isResumedSession, setIsResumedSession] = useState(false)
  const [expandedSections, setExpandedSections] = useState({})
  const [messageDepthPreference, setMessageDepthPreference] = useState({})
  const [sessionSummary, setSessionSummary] = useState(null)
  const [showSessionEnd, setShowSessionEnd] = useState(false)
  const [showQuiz, setShowQuiz] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [speechError, setSpeechError] = useState(null)
  const [speechRecognizer, setSpeechRecognizer] = useState(null)
  const [feedbackSubmitted, setFeedbackSubmitted] = useState({})  // Track which messages have feedback
  const [feedbackCounts, setFeedbackCounts] = useState({})  // Store feedback stats
  const navigate = useNavigate()
  const location = useLocation()

  // Load resumed session on mount
  useEffect(() => {
    console.log('[LEARNING] 📍 Location state changed:', location.state)
    const resumeSessionId = location.state?.resumeSessionId || location.state?.sessionId
    console.log('[LEARNING] Checking for resumed session:', resumeSessionId)
    if (resumeSessionId) {
      console.log('[LEARNING] ✅ Found resumeSessionId, loading session...')
      loadResumedSession(resumeSessionId)
    } else {
      console.log('[LEARNING] ℹ️  No resumeSessionId in location.state')
    }
  }, [location.state])

  const loadResumedSession = async (sessionId) => {
    console.log('[LEARNING] Loading resumed session:', sessionId)
    setLoading(true)
    try {
      console.log('[LEARNING] Fetching session from: /api/session/' + sessionId)
      const res = await fetch(`/api/session/${sessionId}`)
      const data = await res.json()
      
      console.log('[LEARNING] Session data received:', data)
      console.log('[LEARNING] Response full object:',JSON.stringify(data))
      console.log('[LEARNING] Messages array:', data.messages)
      console.log('[LEARNING] Messages count:', data.messages?.length || 0)

      // Check if session data is valid
      if (!data.error && data.topic) {
        console.log('[LEARNING] ✅ Session loaded successfully')
        console.log('[LEARNING] Topic:', data.topic)
        console.log('[LEARNING] Messages count:', data.messages?.length || 0)
        console.log('[LEARNING] Status:', data.status)
        console.log('[LEARNING] Accumulated duration:', data.accumulated_duration, 'seconds')
        console.log('[LEARNING] Setting session state and displaying chat...')
        
        setSessionId(sessionId)
        setTopic(data.topic)
        setMessages(data.messages || [])
        setEmotion(data.emotion || 'neutral')
        setIsSessionActive(true)
        setIsResumedSession(true)
        setStepCount(data.message_count || data.messages?.length || 0)
        setAccumulatedTime(data.accumulated_duration || 0)
        setElapsedTime(0)
        console.log('[LEARNING] ✅ All state updated successfully')
        console.log('[LEARNING] Messages state set to:', data.messages)
      } else {
        console.error('[LEARNING] ❌ Error in session data:', data.error || 'Invalid session structure')
        console.error('[LEARNING] Has topic?', !!data.topic)
        console.error('[LEARNING] Has messages?', data.messages !== undefined)
        alert('Failed to load session: ' + (data.error || 'Invalid session data'))
      }
    } catch (error) {
      console.error('[LEARNING] ❌ Error resuming session:', error)
      alert('Failed to resume session: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  // Initialize Speech Recognition on mount
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'en-US'
      
      recognition.onstart = () => {
        setIsListening(true)
        setSpeechError(null)
      }
      
      recognition.onresult = (event) => {
        let transcript = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcriptSegment = event.results[i][0].transcript
          transcript += transcriptSegment
        }
        
        // Update input field with transcript
        if (event.results[event.results.length - 1].isFinal) {
          setInput(prev => prev + (prev ? ' ' : '') + transcript)
          setIsListening(false)
        }
      }
      
      recognition.onerror = (event) => {
        setSpeechError(`Speech recognition error: ${event.error}`)
        setIsListening(false)
      }
      
      recognition.onend = () => {
        setIsListening(false)
      }
      
      setSpeechRecognizer(recognition)
    }
  }, [])

  const startSpeechInput = () => {
    if (speechRecognizer) {
      setSpeechError(null)
      speechRecognizer.start()
    } else {
      setSpeechError('Speech recognition not supported in your browser. Try Chrome, Edge, or Safari.')
    }
  }

  const stopSpeechInput = () => {
    if (speechRecognizer) {
      speechRecognizer.stop()
      setIsListening(false)
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isListening) {
        stopSpeechInput()
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isListening, speechRecognizer])

  // Persist settings
  useEffect(() => {
    localStorage.setItem('echoFontSize', fontSize)
  }, [fontSize])

  useEffect(() => {
    localStorage.setItem('echoTTS', textToSpeechEnabled)
  }, [textToSpeechEnabled])

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

  // Text-to-speech handler with state tracking
  const handleTextToSpeech = (text) => {
    if (!text || text.trim().length === 0) return
    if (!textToSpeechEnabled) return // Only speak if TTS is enabled
    
    // Stop any ongoing speech first
    window.speechSynthesis.cancel()
    setIsSpeaking(true)
    
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.85
    utterance.pitch = 1.0
    utterance.volume = 1.0
    
    // Track speaking state
    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => {
      setIsSpeaking(false)
      window.speechSynthesis.cancel()
    }
    utterance.onerror = () => {
      setIsSpeaking(false)
      window.speechSynthesis.cancel()
    }
    
    window.speechSynthesis.speak(utterance)
  }

  // Stop current speaking
  const stopSpeaking = () => {
    window.speechSynthesis.cancel()
    setIsSpeaking(false)
  }

  // ✅ FIX 1: Clean text fragments from LLM output
  const cleanTextFragment = (text) => {
    if (!text || typeof text !== 'string') return ""
    
    text = text.trim()
    if (!text) return ""
    
    // Remove broken starting fragments like "s.", ".c", "..."
    if (/^[^A-Za-z0-9]+/.test(text) && text.length < 10) {
      return ""
    }
    
    // Remove single-letter garbage like "s." at start
    if (/^[a-zA-Z]\.($|\s)/.test(text)) {
      return ""
    }
    
    return text
  }

  // ✅ FIX 2: Clamp to max sentences (hard guard)
  const limitSentences = (text, maxSentences = 5) => {
    if (!text || typeof text !== 'string') return ""
    
    text = text.trim()
    if (!text) return ""
    
    // Split on sentence boundaries
    let sentences = text.split('. ')
    if (sentences.length === 1) sentences = text.split('! ')
    if (sentences.length === 1) sentences = text.split('? ')
    
    // Limit
    const limited = sentences.slice(0, maxSentences)
    let result = limited.join('. ')
    
    // Ensure ends with punctuation
    if (result && !result.match(/[.!?]$/)) {
      if (text.match(/[.!?]$/)) {
        result += text.match(/[.!?]$/)[0]
      }
    }
    
    return result.trim()
  }

  // ✅ FIX 3: Render naturally without headers (ChatGPT style)
  const renderNaturalResponse = (content) => {
    if (!content || typeof content !== 'string') return ""
    
    // Clean first
    content = cleanTextFragment(content)
    if (!content) return ""
    
    // Remove any remaining header-style text
    content = content
      .replace(/^(📘|📌|❓|🚀)\s*(?:EXPLANATION|EXAMPLE|QUESTION|WHAT'S YOUR THINKING|Your Turn|Go Deeper)[:\n]*/gi, '')
      .trim()
    
    return content
  }

  // Parse response into detailed sections
  const parseResponseSections = (content) => {
    const sections = []

    // Extract EXPLANATION section (📘 EXPLANATION ... 📌) - More flexible pattern
    let explanationMatch = content.match(/📘\s*EXPLANATION\s*\n([\s\S]*?)(?=📌|❓|\[optional|$)/i)
    if (!explanationMatch) {
      // Fallback: try without emoji requirement
      explanationMatch = content.match(/(?:EXPLANATION|Explanation)\s*[:\n]([\s\S]*?)(?=📌|EXAMPLE|❓|QUESTION|\[optional|$)/i)
    }
    if (explanationMatch) {
      const text = cleanTextFragment(explanationMatch[1].trim())
      if (text.length > 0) {
        sections.push({
          type: 'explanation',
          icon: '📘',
          title: 'Explanation',
          content: text,
          expandable: true
        })
      }
    }

    // Extract EXAMPLE section (📌 EXAMPLE ... ❓) - More flexible pattern
    let exampleMatch = content.match(/📌\s*EXAMPLE\s*\n([\s\S]*?)(?=❓|\[optional|$)/i)
    if (!exampleMatch) {
      // Fallback: try without emoji requirement
      exampleMatch = content.match(/(?:EXAMPLE|Example)\s*[:\n]([\s\S]*?)(?=❓|QUESTION|Your Turn|\[optional|$)/i)
    }
    if (exampleMatch) {
      const text = cleanTextFragment(exampleMatch[1].trim())
      if (text.length > 0) {
        sections.push({
          type: 'example',
          icon: '📌',
          title: 'Example',
          content: text,
          expandable: false
        })
      }
    }

    // Extract QUESTION section (❓ ... [optional or end]) - More flexible pattern
    let questionMatch = content.match(/❓\s*(?:WHAT'S YOUR THINKING\?|QUESTION)?\s*\n?([\s\S]*?)(?=\[optional|$)/i)
    if (!questionMatch) {
      // Fallback: try without emoji requirement
      questionMatch = content.match(/(?:QUESTION|YOUR THINKING|Your Turn)\s*[:\n]?([\s\S]*?)(?=\[optional|$)/i)
    }
    if (questionMatch) {
      const text = cleanTextFragment(questionMatch[1].trim())
      // Only include if text is substantial (not just garbage)
      if (text.length > 3) {
        sections.push({
          type: 'question',
          icon: '❓',
          title: 'Your Turn',
          content: text,
          expandable: false
        })
      }
    }

    // Extract [Optional] sections
    const optionalMatch = content.match(/\[optional[^\]]*\]([\s\S]*?)$/i)
    if (optionalMatch) {
      const text = cleanTextFragment(optionalMatch[1].trim())
      if (text.length > 0) {
        sections.push({
          type: 'optional',
          icon: '🚀',
          title: 'Go Deeper (Optional)',
          content: text,
          expandable: true,
          isOptional: true
        })
      }
    }

    return sections.length > 0 ? sections : [{ type: 'raw', content: renderNaturalResponse(content) }]
  }

  // Toggle section expansion
  const toggleSection = (messageIdx, sectionIdx) => {
    const key = `${messageIdx}-${sectionIdx}`
    setExpandedSections(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  // Generate session summary with AI-extracted concepts
  const generateSessionSummary = async () => {
    if (!sessionId) return

    let topicsLearned = []

    // Try to extract concepts using AI (new endpoint)
    try {
      const response = await fetch(`/api/session/extract-concepts/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      const data = await response.json()
      
      if (data.concepts && Array.isArray(data.concepts) && data.concepts.length > 0) {
        topicsLearned = data.concepts
        console.log('[SUMMARY] AI-extracted concepts:', topicsLearned)
      } else {
        console.log('[SUMMARY] No concepts extracted, using fallback')
      }
    } catch (error) {
      console.error('[SUMMARY] Error extracting concepts:', error)
    }

    // Fallback: use regex if no concepts extracted
    if (topicsLearned.length === 0) {
      topicsLearned = Array.from(new Set(
        messages
          .filter(m => m.role === 'assistant')
          .flatMap(m => m.content.match(/\b[A-Z][a-z]+(?:\s+[a-z]+)*/g) || [])
          .slice(0, 5)
      ))
    }

    // COUNT EMOTIONS FROM AI MESSAGES (each has emotion data)
    const aiMessages = messages.filter(m => m.role === 'assistant')
    const assistantMessagesExchanged = aiMessages.length
    
    // DEBUG: Log all AI messages and their emotions
    console.log('[SUMMARY] AI Messages for emotion counting:', aiMessages.map(m => ({ 
      content: m.content.substring(0, 50) + '...', 
      emotion: m.emotion 
    })))
    
    const emotionCounts = {
      engaged: aiMessages.filter(m => m.emotion && m.emotion.toLowerCase() === 'engaged').length,
      confused: aiMessages.filter(m => m.emotion && m.emotion.toLowerCase() === 'confused').length,
      frustrated: aiMessages.filter(m => m.emotion && m.emotion.toLowerCase() === 'frustrated').length,
      neutral: aiMessages.filter(m => !m.emotion || m.emotion.toLowerCase() === 'neutral').length
    }
    
    const engagementPercent = assistantMessagesExchanged > 0
      ? Math.round((emotionCounts.engaged / assistantMessagesExchanged) * 100)
      : 0
    
    console.log('[SUMMARY] Emotion counts:', emotionCounts, 'Engagement %:', engagementPercent)

    const totalTime = accumulatedTime + elapsedTime
    
    return {
      topic,
      duration: formatTime(totalTime),
      totalSeconds: totalTime,
      messagesExchanged: messages.length,
      assistantMessagesExchanged: assistantMessagesExchanged,
      engagementPercent: engagementPercent,
      topicsLearned: topicsLearned,
      dominantEmotion: emotion,
      emotionJourney: emotionCounts,
      completionTime: new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true }),
      completionDate: new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }),
      stepCount: stepCount,
      sessionId: sessionId
    }
  }

  // Download session summary as text file
  const downloadSessionSummary = () => {
    if (!sessionSummary) return

    const summary = `
╔════════════════════════════════════════════════════════════╗
║                    SESSION SUMMARY REPORT                  ║
╚════════════════════════════════════════════════════════════╝

📚 TOPIC STUDIED
  Topic: ${sessionSummary.topic}
  
⏱️  SESSION DURATION
  Total Time: ${sessionSummary.duration} (${sessionSummary.totalSeconds} seconds)
  Completed At: ${sessionSummary.completionDate} ${sessionSummary.completionTime}

💬 ENGAGEMENT METRICS
  Total Messages: ${sessionSummary.messagesExchanged}
  Assistant Responses: ${sessionSummary.assistantMessagesExchanged}
  Learning Steps: ${sessionSummary.stepCount}
  Dominant Emotion: ${emotionStyle.emoji} ${emotionStyle.label}

😊 EMOTION BREAKDOWN
  🟢 Engaged: ${sessionSummary.emotionJourney.engaged} times
  🟡 Neutral: ${sessionSummary.emotionJourney.neutral} times
  🟠 Confused: ${sessionSummary.emotionJourney.confused} times
  🔴 Frustrated: ${sessionSummary.emotionJourney.frustrated} times

📖 KEY CONCEPTS COVERED
  ${sessionSummary.topicsLearned.map(t => `  • ${t}`).join('\n')}

🎯 PERFORMANCE
  Engagement Level: ${sessionSummary.engagementPercent}%
  Learning Continuity: Excellent (No major frustration spikes)

════════════════════════════════════════════════════════════
  Generated: ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
Session ID: ${sessionSummary.sessionId}
════════════════════════════════════════════════════════════
    `

    const blob = new Blob([summary], { type: 'text/plain' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `EchoConnect_${sessionSummary.topic}_${new Date().getTime()}.txt`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  // Download entire chat + summary as PDF
  const downloadChatAsPDF = async () => {
    if (messages.length === 0 || !sessionSummary) return

    const jsPDF = (await import('jspdf')).default
    const pdf = new jsPDF('p', 'mm', 'a4')
    
    // Set UTF-8 encoding and proper font for unicode support
    pdf.setLanguage('en')
    
    let yPosition = 15
    const pageHeight = pdf.internal.pageSize.getHeight()
    const pageWidth = pdf.internal.pageSize.getWidth()
    const leftMargin = 12
    const lineHeight = 5
    const contentWidth = pageWidth - 2 * leftMargin

    // Helper function to add text with wrapping
    const addWrappedText = (text, fontSize, isBold = false, color = [0, 0, 0]) => {
      // Ensure text is properly decoded and escaped
      let processedText = text
      if (typeof text !== 'string') {
        processedText = String(text)
      }
      
      // Replace any control characters that might cause issues
      processedText = processedText
        .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '') // Remove control characters
        .trim()
      
      pdf.setFontSize(fontSize)
      pdf.setFont(undefined, isBold ? 'bold' : 'normal')
      pdf.setTextColor(color[0], color[1], color[2])

      const lines = pdf.splitTextToSize(processedText, contentWidth)
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
    addContent(sessionSummary.topic)
    yPosition += 2

    // Duration
    addSectionHeader('SESSION DURATION')
    addContent(`Total Time: ${sessionSummary.duration}`)
    addContent(`Total Seconds: ${sessionSummary.totalSeconds}`)
    yPosition += 2

    // Stats
    addSectionHeader('ENGAGEMENT METRICS')
    addContent(`Total Messages: ${sessionSummary.messagesExchanged}`)
    addContent(`Assistant Responses: ${sessionSummary.assistantMessagesExchanged}`)
    addContent(`Learning Steps: ${sessionSummary.stepCount}`)
    addContent(`Engagement Level: ${sessionSummary.engagementPercent}%`)
    yPosition += 2

    // Emotion Journey
    addSectionHeader('EMOTION BREAKDOWN')
    addContent(`Engaged: ${sessionSummary.emotionJourney.engaged} times`)
    addContent(`Neutral: ${sessionSummary.emotionJourney.neutral} times`)
    addContent(`Confused: ${sessionSummary.emotionJourney.confused} times`)
    addContent(`Frustrated: ${sessionSummary.emotionJourney.frustrated} times`)
    yPosition += 2

    // Key Concepts
    addSectionHeader('KEY CONCEPTS COVERED')
    sessionSummary.topicsLearned.forEach(concept => {
      addContent(`- ${concept}`)
    })
    yPosition += 3

    // Add page break
    pdf.addPage()
    yPosition = 15

    // CHAT SECTION
    pdf.setFillColor(230, 240, 250)
    pdf.rect(12, yPosition - 4, pageWidth - 24, 10, 'F')
    addWrappedText('FULL CHAT TRANSCRIPT', 14, true, [0, 100, 150])
    addWrappedText(`Topic: ${topic}`, 8, false, [100, 100, 100])
    addWrappedText(`Date: ${new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}`, 8, false, [100, 100, 100])
    yPosition += 3

    // Chat messages
    messages.forEach((msg, idx) => {
      const isUser = msg.role === 'user'
      const label = isUser ? 'YOU' : 'AI TUTOR'
      
      addWrappedText(`[${label}]`, 9, true, isUser ? [59, 130, 246] : [34, 197, 94])
      
      // Properly handle message content - ensure it's a string and properly encoded
      let content = msg.content || ''
      if (typeof content !== 'string') {
        content = String(content)
      }
      
      // Clean up any encoding issues
      content = content
        .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '') // Remove control characters
        .replace(/\s+/g, ' ') // Normalize whitespace
        .trim()
      
      // Truncate long messages
      const truncatedContent = content.substring(0, 800)
      addWrappedText(truncatedContent, 8, false, [50, 50, 50])
      yPosition += 2
    })

    // Footer
    yPosition += 3
    if (yPosition > pageHeight - 10) {
      pdf.addPage()
      yPosition = 15
    }
    addWrappedText(`Generated: ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}`, 7, false, [120, 120, 120])
    addWrappedText(`Session ID: ${sessionSummary.sessionId}`, 7, false, [120, 120, 120])
    addWrappedText(`Total Messages: ${messages.length}`, 7, false, [120, 120, 120])

    pdf.save(`EchoConnect_${sessionSummary.topic}_${new Date().getTime()}.pdf`)
  }

  // Get context-aware adaptive quick actions
  const getContextualActions = () => {
    if (messages.length === 0) return ['Start', 'Ready?', 'Confused', 'Slow']
    
    const lastMessage = messages[messages.length - 1]
    
    if (lastMessage.role === 'assistant') {
      // After AI explanation - emotion-based
      if (emotion?.includes('confused')) {
        return ['Simplify', 'Example', 'Explain', 'Help']
      } else if (emotion?.includes('engaged')) {
        return ['Deeper', 'Challenge', 'More', 'Got it']
      } else if (emotion?.includes('frustrated')) {
        return ['Break', 'Restart', 'Hint', 'Retry']
      } else {
        return ['Summary', 'Example', 'Understood', 'Next']
      }
    }
    
    // After user response
    return ['Right', 'Nope', 'More', 'Next']
  }

  const getThemeColors = () => {
    return theme === 'dark' ? {
      bg: '#0f172a',
      bgSecondary: '#1e293b',
      border: '#475569',
      text: '#e2e8f0',
      textMuted: '#94a3b8',
      accent: '#06b6d4',
      explanationBg: '#1e3a4c',
      explanationBorder: '#3b82f6',
      exampleBg: '#1e3a2c',
      exampleBorder: '#22c55e',
      questionBg: '#3a2c1e',
      questionBorder: '#f97316'
    } : {
      bg: '#f8fafc',
      bgSecondary: '#f1f5f9',
      border: '#cbd5e1',
      text: '#1e293b',
      textMuted: '#475569',
      accent: '#0891b2',
      explanationBg: '#e0f2fe',
      explanationBorder: '#0284c7',
      exampleBg: '#dcfce7',
      exampleBorder: '#16a34a',
      questionBg: '#fed7aa',
      questionBorder: '#ea580c'
    }
  }

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
      console.log('[LEARNING] Starting session - userId:', userId, 'topic:', topic)
      
      if (!userId) {
        console.error('[LEARNING] No user_id found in localStorage')
        alert('Please login first')
        setLoading(false)
        return
      }
      
      console.log('[LEARNING] Sending POST to /session/start-teaching with:', { user_id: userId, topic })
      
      const res = await fetch('/api/session/start-teaching', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, topic }),
      })

      const data = await res.json()
      
      console.log('[LEARNING] Response from API:', data)
      
      if (!res.ok || data.error) {
        console.error('[LEARNING] Error from API:', data)
        setLoading(false)
        return
      }
      
      console.log('[LEARNING] Session created successfully:', data.session_id)
      console.log('[LEARNING] Session user_id:', data.user_id)
      console.log('[LEARNING] Session status:', data.status)
      console.log('[LEARNING] Initial emotion from API:', data.emotion)  // ← DEBUG
      setSessionId(data.session_id)
      setIsSessionActive(true)
      setElapsedTime(0)
      setAccumulatedTime(0)
      setIsResumedSession(false)
      setStepCount(1)
      
      // STORE INITIAL MESSAGE WITH FULL METADATA SNAPSHOT
      const initialMessage = {
        role: 'assistant',
        content: `${data.explanation}\n\n${data.example}\n\n${data.question}`,
        emotion: data.emotion || 'neutral',
        timestamp: Date.now(),
        concept: topic
      }
      console.log('[LEARNING] Storing initial message with metadata:', {emotion: initialMessage.emotion, timestamp: initialMessage.timestamp})
      setMessages([initialMessage])
      setEmotion(data.emotion || 'neutral')
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
      // Generate summary before ending
      const summary = await generateSessionSummary()
      setSessionSummary(summary)
      
      // Save summary to localStorage for persistence
      localStorage.setItem('lastSessionSummary', JSON.stringify(summary))
      localStorage.setItem('lastSessionSummaryTime', new Date().toISOString())

      await fetch('/api/session/end', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })

      // CLOSE SESSION AND SHOW SUMMARY IN FULL-PAGE VIEW
      setIsSessionActive(false)
      setShowSessionEnd(true)
    } catch (error) {
      console.error('Error:', error)
    }
  }

  // Handle navigation after viewing summary
  const handleLeaveSummary = (destination = 'dashboard') => {
    setSessionId(null)
    setTopic('')
    setElapsedTime(0)
    setAccumulatedTime(0)
    setIsResumedSession(false)
    setMessages([])
    setInput('')
    setEmotion('neutral')
    setStepCount(0)
    setUserReactions({})
    setExpandedSections({})
    setShowSessionEnd(false)
    
    if (destination === 'dashboard') {
      navigate('/dashboard')
    } else if (destination === 'history') {
      navigate('/history', { state: { resumeSessionId: sessionSummary?.sessionId } })
    }
  }

  const handleQuickResponse = (response) => {
    setInput(response)
  }

  const handleReaction = (messageIdx, reaction) => {
    setUserReactions(prev => ({
      ...prev,
      [messageIdx]: prev[messageIdx] === reaction ? null : reaction
    }))
  }

  const handleFeedback = async (messageIdx, helpful) => {
    if (!sessionId) return
    
    const msg = messages[messageIdx]
    if (msg.role !== 'assistant') return  // Only for AI messages
    
    // Prevent double-submission
    if (feedbackSubmitted[messageIdx]) return
    
    try {
      const response = await fetch('/api/feedback/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message_index: messageIdx,
          helpful: helpful,
          message_content: msg.content,
          emotion: msg.emotion || 'neutral',
          concept: topic
        })
      })
      
      if (!response.ok) {
        console.error('[FEEDBACK] Failed to submit:', response.statusText)
        return
      }
      
      const data = await response.json()
      console.log('[FEEDBACK] ✅ Submitted:', data.feedback_id)
      
      // Mark as submitted and show positive feedback
      setFeedbackSubmitted(prev => ({
        ...prev,
        [messageIdx]: helpful ? '👍' : '👎'
      }))
      
      // After 2 seconds, reset visual feedback
      setTimeout(() => {
        setFeedbackSubmitted(prev => ({
          ...prev,
          [messageIdx]: null
        }))
      }, 2000)
    } catch (error) {
      console.error('[FEEDBACK] Error:', error)
    }
  }

  const handleSubmit = async () => {
    if (!input.trim() || !sessionId) return
    
    const userMessage = {
      role: 'user',
      content: input
    }
    setMessages(prev => [...prev, userMessage])
    setLoading(true)
    
    try {
      console.log('[SEND] Request:', { session_id: sessionId, text: input })
      const res = await fetch('/api/session/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          session_id: sessionId,
          text: input
        }),
      })

      // Parse response with error handling
      const text = await res.text()
      console.log('[RECV] Response status:', res.status)
      console.log('[RECV] Response text (first 200 chars):', text.substring(0, 200))
      
      if (!text) {
        throw new Error(`Empty response from server (status ${res.status})`)
      }
      
      let data
      try {
        data = JSON.parse(text)
      } catch(e) {
        console.error('[RECV] JSON parse failed. Full response:', text)
        throw new Error(`Invalid JSON from server: ${text.substring(0, 300)}`)
      }
      
      if (data.error) {
        console.error('Error:', data)
        setLoading(false)
        setInput('')
        return
      }

      console.log('[LEARNING] Raw API Response:', data)
      console.log('[LEARNING] Response text:', data.response)
      console.log('[LEARNING] Response emotion:', data.emotion)

      // STORE FULL MESSAGE METADATA SNAPSHOT (not global state)
      const aiMessage = {
        role: 'assistant',
        content: data.response,
        emotion: data.emotion || 'neutral',
        timestamp: Date.now(),
        concept: topic
      }
      console.log('[LEARNING] Storing AI message with metadata snapshot:', {emotion: aiMessage.emotion, timestamp: aiMessage.timestamp})
      setMessages(prev => [...prev, aiMessage])
      setEmotion(data.emotion || 'neutral')
      setStepCount(prev => prev + 1)
      setInput('')
      
      handleTextToSpeech(data.response)
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  // FULL-PAGE SUMMARY VIEW (shows when session ends)
  if (showQuiz && sessionId) {
    return (
      <SessionQuiz 
        sessionId={sessionId} 
        onClose={() => setShowQuiz(false)}
        theme={theme}
      />
    )
  }

  if (showSessionEnd && sessionSummary && !isSessionActive) {
    const colors = getThemeColors()
    
    return (
      <div style={{display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: colors.bg, color: colors.text, padding: '18px 14px', maxWidth: '1100px', margin: '0 auto', width: '100%', boxSizing: 'border-box', fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', lineHeight: 1.5, letterSpacing: '0.01em'}}>
        {/* HEADER */}
        <div style={{textAlign: 'center', marginBottom: '20px'}}>
          <h1 style={{fontSize: '32px', fontWeight: '700', margin: '0 0 6px 0', color: colors.accent}}>🎉 Session Complete!</h1>
          <p style={{fontSize: '14px', color: colors.textMuted, margin: '0'}}>Great work — here's your learning summary.</p>
        </div>

        {/* MAIN METRICS */}
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '20px'}}>
          <div style={{backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '16px', borderRadius: '10px', textAlign: 'center', boxShadow: '0 8px 24px rgba(2,6,23,0.08)'}}>
            <div style={{fontSize: '12px', color: colors.textMuted, marginBottom: '8px', fontWeight: '600'}}>⏱️ Duration</div>
            <div style={{fontSize: '28px', fontWeight: 'bold', color: '#22c55e'}}>{sessionSummary.duration}</div>
          </div>
          <div style={{backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '16px', borderRadius: '10px', textAlign: 'center', boxShadow: '0 8px 24px rgba(2,6,23,0.08)'}}>
            <div style={{fontSize: '12px', color: colors.textMuted, marginBottom: '8px', fontWeight: '600'}}>💬 Messages</div>
            <div style={{fontSize: '28px', fontWeight: 'bold', color: '#3b82f6'}}>{sessionSummary.messagesExchanged}</div>
          </div>
          <div style={{backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '16px', borderRadius: '10px', textAlign: 'center', boxShadow: '0 8px 24px rgba(2,6,23,0.08)'}}>
            <div style={{fontSize: '12px', color: colors.textMuted, marginBottom: '8px', fontWeight: '600'}}>📈 Steps</div>
            <div style={{fontSize: '28px', fontWeight: 'bold', color: '#f59e0b'}}>{sessionSummary.stepCount}</div>
          </div>
          <div style={{backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '16px', borderRadius: '10px', textAlign: 'center', boxShadow: '0 8px 24px rgba(2,6,23,0.08)'}}>
            <div style={{fontSize: '12px', color: colors.textMuted, marginBottom: '8px', fontWeight: '600'}}>🎯 Engagement</div>
            <div style={{fontSize: '28px', fontWeight: 'bold', color: '#06b6d4'}}>{Math.round((sessionSummary.emotionJourney.engaged / sessionSummary.messagesExchanged) * 100)}%</div>
          </div>
        </div>

        {/* TOPIC & CONCEPTS */}
        <div style={{backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '16px', borderRadius: '10px', marginBottom: '20px', boxShadow: '0 8px 24px rgba(2,6,23,0.06)'}}>
          <h2 style={{margin: '0 0 16px 0', color: colors.accent, fontSize: '18px'}}>📚 Topic Studied</h2>
          <p style={{margin: '0 0 12px 0', fontSize: '16px', fontWeight: '700', color: colors.text}}>{sessionSummary.topic}</p>
          <p style={{margin: '0 0 10px 0', fontSize: '13px', color: colors.textMuted}}>Key concepts:</p>
          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
            {sessionSummary.topicsLearned.map((t, idx) => (
              <span key={idx} style={{backgroundColor: 'rgba(148,163,184,0.06)', padding: '6px 12px', borderRadius: '16px', fontSize: '12px', color: colors.accent, fontWeight: '600'}}>{t}</span>
            ))}
          </div>
        </div>

        {/* EMOTION BREAKDOWN */}
        <div style={{backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '16px', borderRadius: '10px', marginBottom: '20px', boxShadow: '0 8px 24px rgba(2,6,23,0.06)'}}>
          <h2 style={{margin: '0 0 16px 0', color: colors.accent, fontSize: '18px'}}>😊 Emotion Journey</h2>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px'}}>
            <div style={{backgroundColor: colors.bg, padding: '16px', borderRadius: '8px', borderLeft: '2px solid #22c55e'}}>
              <p style={{margin: '0 0 8px 0', fontSize: '12px', color: colors.textMuted}}>🟢 Engaged</p>
              <p style={{margin: '0', fontSize: '24px', fontWeight: 'bold', color: '#22c55e'}}>{sessionSummary.emotionJourney.engaged}x</p>
            </div>
            <div style={{backgroundColor: colors.bg, padding: '16px', borderRadius: '8px', borderLeft: '2px solid #64748b'}}>
              <p style={{margin: '0 0 8px 0', fontSize: '12px', color: colors.textMuted}}>🟡 Neutral</p>
              <p style={{margin: '0', fontSize: '24px', fontWeight: 'bold', color: '#64748b'}}>{sessionSummary.emotionJourney.neutral}x</p>
            </div>
            <div style={{backgroundColor: colors.bg, padding: '16px', borderRadius: '8px', borderLeft: '2px solid #eab308'}}>
              <p style={{margin: '0 0 8px 0', fontSize: '12px', color: colors.textMuted}}>🟠 Confused</p>
              <p style={{margin: '0', fontSize: '24px', fontWeight: 'bold', color: '#eab308'}}>{sessionSummary.emotionJourney.confused}x</p>
            </div>
            <div style={{backgroundColor: colors.bg, padding: '16px', borderRadius: '8px', borderLeft: '2px solid #ef4444'}}>
              <p style={{margin: '0 0 8px 0', fontSize: '12px', color: colors.textMuted}}>🔴 Frustrated</p>
              <p style={{margin: '0', fontSize: '24px', fontWeight: 'bold', color: '#ef4444'}}>{sessionSummary.emotionJourney.frustrated}x</p>
            </div>
          </div>
        </div>

        {/* ACTION BUTTONS */}
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '10px', marginBottom: '12px'}}>
          <button
            onClick={() => handleLeaveSummary('history')}
            style={{padding: '10px 14px', backgroundColor: '#22c55e', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'all 0.2s'}}
            onMouseEnter={(e) => e.target.style.opacity = '0.95'}
            onMouseLeave={(e) => e.target.style.opacity = '1'}
          >
            ⏱️ Resume
          </button>
          <button
            onClick={() => setShowQuiz(true)}
            style={{padding: '10px 14px', backgroundColor: '#10b981', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'all 0.2s'}}
            onMouseEnter={(e) => e.target.style.opacity = '0.95'}
            onMouseLeave={(e) => e.target.style.opacity = '1'}
          >
            🎯 Quiz
          </button>
          <button
            onClick={downloadChatAsPDF}
            style={{padding: '10px 14px', backgroundColor: '#8b5cf6', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'all 0.2s'}}
            onMouseEnter={(e) => e.target.style.opacity = '0.95'}
            onMouseLeave={(e) => e.target.style.opacity = '1'}
          >
            💬 Chat
          </button>
          <button
            onClick={() => handleLeaveSummary('dashboard')}
            style={{padding: '10px 14px', backgroundColor: '#3b82f6', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', transition: 'all 0.2s'}}
            onMouseEnter={(e) => e.target.style.opacity = '0.95'}
            onMouseLeave={(e) => e.target.style.opacity = '1'}
          >
            🏠 Dashboard
          </button>
        </div>

        {/* FOOTER INFO */}
        <div style={{textAlign: 'center', color: colors.textMuted, fontSize: '12px', borderTop: '1px solid rgba(148,163,184,0.04)', paddingTop: '20px', marginTop: 'auto'}}>
          <p style={{margin: '0'}}>Generated: {new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}</p>
          <p style={{margin: '4px 0 0 0'}}>Session ID: {sessionSummary.sessionId}</p>
        </div>
      </div>
    )
  }

  if (!isSessionActive) {
    const colors = getThemeColors()
    
    // Suggested topics for quick learning
    const suggestedTopics = [
      { icon: '📐', label: 'Geometry', topic: 'Basic Geometry Concepts' },
      { icon: '🔬', label: 'Science', topic: 'Introduction to Physics' },
      { icon: '📖', label: 'Literature', topic: 'Shakespeare and Poetry' },
      { icon: '💻', label: 'Programming', topic: 'Web Development Basics' },
      { icon: '🌍', label: 'History', topic: 'Ancient Civilizations' },
      { icon: '🎨', label: 'Art', topic: 'Color Theory and Design' }
    ]
    
    const handleSuggestedTopic = (suggestedTopic) => {
      setTopic(suggestedTopic)
    }
    
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: colors.bg,
        background: `linear-gradient(135deg, ${colors.bg} 0%, rgba(6, 182, 212, 0.03) 100%)`,
        padding: '20px',
        animation: 'fadeIn 0.6s ease-out'
      }}>
        <style>{`
          @keyframes fadeIn {
            from {
              opacity: 0;
              transform: translateY(10px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          @keyframes slideUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          @keyframes pulse {
            0%, 100% {
              opacity: 1;
            }
            50% {
              opacity: 0.7;
            }
          }
        `}</style>
        
        <div style={{
          maxWidth: '640px',
          width: '100%',
          animation: 'slideUp 0.8s ease-out'
        }}>
          {/* Header Section */}
          <div style={{
            textAlign: 'center',
            marginBottom: '48px'
          }}>
            <h1 style={{
              fontSize: '44px',
              fontWeight: '800',
              marginBottom: '8px',
              color: colors.accent,
              letterSpacing: '-0.02em'
            }}>
              EchoConnect
            </h1>
            <p style={{
              fontSize: '18px',
              color: colors.textMuted,
              marginBottom: '8px',
              fontWeight: '500'
            }}>
              Your Personal AI Tutoring Assistant
            </p>
          </div>

          {/* Input Section */}
          <div style={{
            marginBottom: '40px',
            animation: 'slideUp 1s ease-out'
          }}>
            <div style={{
              position: 'relative',
              marginBottom: '12px'
            }}>
              <input
                type="text"
                placeholder="What do you want to learn today?"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleStartSession()}
                style={{
                  width: '100%',
                  padding: '16px 16px',
                  fontSize: `${fontSize}px`,
                  border: `2px solid ${topic ? colors.accent : 'rgba(148,163,184,0.1)'}`,
                  borderRadius: '12px',
                  backgroundColor: colors.bg,
                  color: colors.text,
                  boxSizing: 'border-box',
                  transition: 'all 0.3s ease',
                  outline: 'none',
                  boxShadow: topic ? `0 0 0 3px rgba(6, 182, 212, 0.1)` : 'none',
                  fontFamily: 'inherit'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = colors.accent
                  e.target.style.boxShadow = `0 0 0 3px rgba(6, 182, 212, 0.1)`
                }}
                onBlur={(e) => {
                  if (!topic) {
                    e.target.style.borderColor = 'rgba(148,163,184,0.1)'
                    e.target.style.boxShadow = 'none'
                  }
                }}
              />
              {topic && (
                <button
                  onClick={() => setTopic('')}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    fontSize: '18px',
                    cursor: 'pointer',
                    opacity: 0.6,
                    transition: 'opacity 0.2s'
                  }}
                  onMouseEnter={(e) => e.target.style.opacity = '1'}
                  onMouseLeave={(e) => e.target.style.opacity = '0.6'}
                >
                  ✕
                </button>
              )}
            </div>
            <p style={{
              fontSize: '12px',
              color: colors.textMuted,
              margin: '6px 0 0 0'
            }}>
              Press Enter or click "Start Learning" to begin
            </p>
          </div>

          {/* Start Button */}
          <button
            onClick={handleStartSession}
            disabled={!topic.trim() || loading}
            style={{
              width: '100%',
              padding: '16px',
              backgroundColor: !topic.trim() || loading ? 'rgba(6, 182, 212, 0.5)' : colors.accent,
              color: '#ffffff',
              border: 'none',
              borderRadius: '12px',
              cursor: !topic.trim() || loading ? 'not-allowed' : 'pointer',
              fontWeight: '700',
              fontSize: `${Math.max(fontSize, 14)}px`,
              transition: 'all 0.3s ease',
              boxShadow: !topic.trim() || loading ? 'none' : '0 8px 16px rgba(6, 182, 212, 0.2)',
              opacity: !topic.trim() || loading ? 0.7 : 1,
              transform: loading ? 'scale(0.98)' : 'scale(1)',
              letterSpacing: '0.5px'
            }}
            onMouseEnter={(e) => {
              if (!(!topic.trim() || loading)) {
                e.target.style.transform = 'scale(1.02)'
                e.target.style.boxShadow = '0 12px 24px rgba(6, 182, 212, 0.3)'
              }
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'scale(1)'
              e.target.style.boxShadow = '0 8px 16px rgba(6, 182, 212, 0.2)'
            }}
          >
            {loading ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ animation: 'pulse 1s ease-in-out infinite' }}>⏳</span>
                Starting...
              </span>
            ) : (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                ✨ Start Learning
              </span>
            )}
          </button>

          {/* Suggested Topics */}
          <div style={{
            marginTop: '48px',
            animation: 'slideUp 1.2s ease-out'
          }}>
            <p style={{
              fontSize: '13px',
              color: colors.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              marginBottom: '16px',
              fontWeight: '600'
            }}>
              ✨ Popular Topics
            </p>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))',
              gap: '12px'
            }}>
              {suggestedTopics.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestedTopic(item.topic)}
                  style={{
                    padding: '14px 12px',
                    backgroundColor: 'rgba(6, 182, 212, 0.08)',
                    border: '1px solid rgba(6, 182, 212, 0.2)',
                    borderRadius: '10px',
                    color: colors.text,
                    cursor: 'pointer',
                    transition: 'all 0.3s ease',
                    fontSize: '12px',
                    fontWeight: '600',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '6px',
                    animation: `slideUp ${0.8 + idx * 0.1}s ease-out`
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(6, 182, 212, 0.15)'
                    e.currentTarget.style.borderColor = colors.accent
                    e.currentTarget.style.transform = 'translateY(-4px)'
                    e.currentTarget.style.boxShadow = '0 8px 12px rgba(6, 182, 212, 0.1)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(6, 182, 212, 0.08)'
                    e.currentTarget.style.borderColor = 'rgba(6, 182, 212, 0.2)'
                    e.currentTarget.style.transform = 'translateY(0)'
                    e.currentTarget.style.boxShadow = 'none'
                  }}
                >
                  <span style={{ fontSize: '24px' }}>{item.icon}</span>
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Footer Tips */}
          <div style={{
            marginTop: '40px',
            padding: '16px',
            backgroundColor: 'rgba(6, 182, 212, 0.05)',
            borderRadius: '10px',
            border: '1px solid rgba(6, 182, 212, 0.1)',
            animation: 'slideUp 1.4s ease-out'
          }}>
            <p style={{
              fontSize: '12px',
              color: colors.textMuted,
              margin: '0',
              lineHeight: '1.6'
            }}>
              💡 <strong>Pro Tip:</strong> Be specific with your topic for better personalized learning. Try "Photosynthesis in plants" instead of just "Biology".
            </p>
          </div>
        </div>
      </div>
    )
  }

  const colors = getThemeColors()
  const emotionStyle = getEmotionStyle(emotion)

  return (
    <div style={{display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden', backgroundColor: colors.bg, color: colors.text, fontSize: `${fontSize}px`}}>
      {/* SIDEBAR */}
      <div style={{
        width: sidebarOpen ? '260px' : '0px',
        backgroundColor: colors.bgSecondary,
        borderRight: sidebarOpen ? '1px solid rgba(148,163,184,0.04)' : 'none',
        padding: sidebarOpen ? '22px' : '0px',
        overflow: 'hidden',
        transition: 'width 0.35s ease, padding 0.35s ease, box-shadow 0.35s ease',
        boxShadow: sidebarOpen ? '2px 0 22px rgba(15, 23, 42, 0.14)' : 'none',
        maxHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        justifyContent: 'flex-start',
        borderRadius: sidebarOpen ? '0 20px 20px 0' : '0',
      }}>
        {sidebarOpen && (
          <>
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px'}}>
              <div>
                <div style={{fontSize: '11px', color: colors.textMuted, textTransform: 'uppercase', letterSpacing: '0.18em', marginBottom: '6px'}}>Session</div>
                <h3 style={{margin: '0', color: colors.accent, fontSize: '20px'}}>📚 Quick View</h3>
              </div>
            </div>
            <div style={{marginBottom: '20px', backgroundColor: colors.bg, border: '1px solid rgba(148,163,184,0.04)', borderRadius: '18px', padding: '18px', boxShadow: '0 6px 16px rgba(2,6,23,0.04)'}}>
              <p style={{fontSize: '11px', color: colors.textMuted, margin: '0 0 8px 0', letterSpacing: '0.08em'}}>Topic</p>
              <p style={{margin: '0 0 16px 0', fontWeight: '700', color: colors.text, fontSize: '15px'}}>{topic}</p>

              <p style={{fontSize: '11px', color: colors.textMuted, margin: '0 0 8px 0', letterSpacing: '0.08em'}}>Time</p>
              <div>
                {isResumedSession ? (
                  <>
                    <p style={{margin: '0 0 6px 0', fontSize: '12px', color: colors.textMuted}}>
                      {formatTime(accumulatedTime + elapsedTime)} total
                    </p>
                    <p style={{margin: '0', fontSize: '10px', color: colors.textMuted}}>
                      continued from {formatTime(accumulatedTime)}
                    </p>
                  </>
                ) : (
                  <p style={{margin: '0', fontWeight: '700', color: colors.accent, fontSize: '18px'}}>
                    {formatTime(elapsedTime)}
                  </p>
                )}
              </div>
            </div>

            <div style={{marginTop: '14px', borderTop: '1px solid rgba(148,163,184,0.04)', paddingTop: '18px'}}>
              <label style={{display: 'flex', alignItems: 'center', gap: '10px', color: colors.text, cursor: 'pointer', marginBottom: '18px', padding: '10px 12px', borderRadius: '16px', backgroundColor: colors.bg}}>
                <input type="checkbox" checked={textToSpeechEnabled} onChange={() => setTextToSpeechEnabled(!textToSpeechEnabled)} />
                <span style={{fontWeight: '600'}}>🔊 Audio</span>
              </label>

              </div>

            <button onClick={handleEndSession} style={{width: '100%', marginTop: '22px', padding: '12px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '14px', cursor: 'pointer', fontWeight: '700', fontSize: '13px'}}>
              Exit Session
            </button>
          </>
        )}
      </div>


      {/* MAIN CONTENT */}
      <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
        {/* HEADER WITH PROGRESS */}
        <div style={{position: 'sticky', top: 0, zIndex: 10, backgroundColor: 'rgba(15, 23, 42, 0.98)', borderBottom: '1px solid rgba(148, 163, 184, 0.14)', padding: '10px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px'}}>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0}}>
            <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{background: 'none', border: 'none', color: colors.accent, cursor: 'pointer', fontSize: '18px', padding: '6px', lineHeight: 1}} title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}>☰</button>
            <div style={{minWidth: 0}}>
              <h2 style={{margin: '0 0 2px 0', color: colors.text, fontSize: '15px', fontWeight: '700', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{topic}</h2>
              <div style={{fontSize: '11px', color: colors.textMuted, letterSpacing: '0.02em'}}>
                {formatTime(accumulatedTime + elapsedTime)}
              </div>
            </div>
          </div>
          
          <div style={{display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0}}>
            <button
              onClick={() => setTextToSpeechEnabled(!textToSpeechEnabled)}
              title={textToSpeechEnabled ? 'Audio ON - Click to disable' : 'Audio OFF - Click to enable'}
              style={{backgroundColor: 'rgba(148, 163, 184, 0.14)', border: '1px solid rgba(148, 163, 184, 0.2)', borderRadius: '999px', color: colors.text, padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px'}}
            >
              {textToSpeechEnabled ? '🔊' : '🔇'}
            </button>
            {isSpeaking && (
              <button
                onClick={stopSpeaking}
                title="Stop speaking"
                style={{background: 'none', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '999px', cursor: 'pointer', fontSize: '14px', padding: '6px 8px', color: '#ef4444'}}
              >
                ⏹
              </button>
            )}

            <div style={{display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '999px', backgroundColor: `rgba(${emotionStyle.color === '#ef4444' ? '239, 68, 68' : emotionStyle.color === '#eab308' ? '234, 179, 8' : emotionStyle.color === '#22c55e' ? '34, 197, 94' : '6, 182, 212'}, 0.12)`, border: `1px solid ${emotionStyle.color}`}}>
              <span style={{fontSize: '13px'}}>{emotionStyle.emoji}</span>
              <span style={{fontSize: '11px', fontWeight: '700', color: emotionStyle.color}}>{emotionStyle.label}</span>
            </div>
          </div>
        </div>
        


        {/* CHAT AREA */}
        <div style={{flex: '1 1 0', minHeight: 0, overflowY: 'auto', padding: '16px 18px', margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '14px', backgroundColor: colors.bg}}>
          {!messages || messages.length === 0 ? (
            <div style={{color: colors.textMuted, textAlign: 'center', padding: '60px 20px'}}>
              <div style={{fontSize: '48px', marginBottom: '16px'}}>📚</div>
              <p style={{fontSize: '16px', fontWeight: 'bold', marginBottom: '8px'}}>Ready to learn?</p>
              <p style={{fontSize: '14px', opacity: 0.8}}>Start a new session or resume where you left off</p>
            </div>
          ) : (
            <>
              {messages.map((msg, msgIdx) => {
                const sections = msg.role === 'assistant' ? parseResponseSections(msg.content) : null
                console.log(`[LEARNING] Message ${msgIdx}:`, { role: msg.role, contentLength: msg.content?.length, contentPreview: msg.content?.substring(0, 100), sections: sections?.length })
                
                return msg.role === 'user' ? (
                  // USER MESSAGE - Minimal outgoing bubble
                  <div key={msgIdx} style={{display: 'flex', justifyContent: 'flex-end', marginBottom: '8px', paddingRight: '28px'}}>
                    <div style={{maxWidth: '680px', width: '100%'}}>
                      <div style={{backgroundColor: 'rgba(96, 165, 250, 0.12)', color: '#f0f9ff', padding: '10px 14px', borderRadius: '12px', wordWrap: 'break-word', fontSize: '13px', lineHeight: '1.5', boxShadow: 'none', border: 'none'}}>
                        <p style={{margin: 0, whiteSpace: 'pre-wrap'}}>{msg.content}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  // AI MESSAGE - Minimal card with softer background
                  <div key={msgIdx} style={{display: 'flex', gap: '10px', marginBottom: '8px', paddingLeft: '12px'}}>
                    <div style={{flex: 1, maxWidth: '900px'}}>
                      {/* TEACHING ADAPTATION BADGES - Uses per-message emotion snapshot */}
                      <div style={{display: 'flex', gap: '6px', marginBottom: '6px', flexWrap: 'wrap', alignItems: 'center'}}>
                        {/* Depth Level Badge - uses msg.emotion, not global emotion */}
                        <span style={{display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: '4px', backgroundColor: msg.emotion === 'very_engaged' || msg.emotion === 'engaged' ? 'rgba(59, 130, 246, 0.1)' : msg.emotion === 'confused' ? 'rgba(234, 179, 8, 0.1)' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(100, 116, 139, 0.1)', border: `1px solid ${msg.emotion === 'very_engaged' || msg.emotion === 'engaged' ? 'rgba(59, 130, 246, 0.4)' : msg.emotion === 'confused' ? 'rgba(234, 179, 8, 0.4)' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(100, 116, 139, 0.3)'}`, fontSize: '11px', fontWeight: '600', color: msg.emotion === 'very_engaged' || msg.emotion === 'engaged' ? '#60a5fa' : msg.emotion === 'confused' ? '#facc15' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? '#f87171' : '#94a3b8'}}>
                          {msg.emotion === 'very_engaged' ? 'Expert' : msg.emotion === 'engaged' ? 'Advanced' : msg.emotion === 'confused' ? 'Beginner' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? 'Support' : 'Intermediate'}
                        </span>
                        
                        {/* Content Type Badge - uses msg.emotion, not global emotion */}
                        <span style={{display: 'inline-flex', alignItems: 'center', gap: '3px', padding: '4px 8px', borderRadius: '4px', backgroundColor: msg.emotion === 'very_engaged' ? 'rgba(168, 85, 247, 0.1)' : msg.emotion === 'engaged' ? 'rgba(34, 197, 94, 0.1)' : msg.emotion === 'confused' ? 'rgba(59, 130, 246, 0.1)' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? 'rgba(249, 115, 22, 0.1)' : 'rgba(107, 114, 128, 0.1)', border: `1px solid ${msg.emotion === 'very_engaged' ? 'rgba(168, 85, 247, 0.4)' : msg.emotion === 'engaged' ? 'rgba(34, 197, 94, 0.4)' : msg.emotion === 'confused' ? 'rgba(59, 130, 246, 0.4)' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? 'rgba(249, 115, 22, 0.4)' : 'rgba(107, 114, 128, 0.3)'}`, fontSize: '10px', fontWeight: '500', color: msg.emotion === 'very_engaged' ? '#d8b4fe' : msg.emotion === 'engaged' ? '#86efac' : msg.emotion === 'confused' ? '#93c5fd' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? '#fdba74' : '#cbd5e1'}}>
                          {msg.emotion === 'very_engaged' ? 'Exploration' : msg.emotion === 'engaged' ? 'Concepts' : msg.emotion === 'confused' ? 'Simplified' : msg.emotion === 'frustrated' || msg.emotion === 'very_frustrated' ? 'Coaching' : 'Balanced'}
                        </span>
                      </div>
                      <div style={{backgroundColor: 'rgba(100, 116, 139, 0.05)', border: 'none', borderRadius: '12px', overflow: 'hidden', padding: '12px'}}>
                        {/* ✅ CHECK: Render naturally if response doesn't have clear headers */}
                        {(!msg.content || !msg.content.includes('📘') && !msg.content.includes('📌') && !msg.content.includes('❓')) ? (
                          // NATURAL CONVERSATION STYLE (new default)
                          <div style={{fontSize: '13px', lineHeight: '1.5', color: colors.text, wordWrap: 'break-word'}}>
                            <p style={{margin: '0 0 8px 0', whiteSpace: 'pre-wrap'}}>{renderNaturalResponse(msg.content)}</p>
                            <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px'}}>
                              {textToSpeechEnabled && (
                                <button
                                  onClick={() => handleTextToSpeech(msg.content)}
                                  disabled={isSpeaking}
                                  style={{display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', fontSize: '11px', backgroundColor: 'transparent', border: `1px solid ${isSpeaking ? 'rgba(96, 165, 250, 0.4)' : 'rgba(96, 165, 250, 0.2)'}`, borderRadius: '4px', cursor: isSpeaking ? 'default' : 'pointer', color: '#60a5fa', fontWeight: '500', transition: 'all 0.2s', opacity: isSpeaking ? 0.7 : 1}}
                                  title="Read message aloud"
                                >
                                  {isSpeaking ? '⏸' : '🔊'}
                                </button>
                              )}
                              
                              {/* FEEDBACK BUTTONS - Was this helpful? */}
                              <button
                                onClick={() => handleFeedback(msgIdx, true)}
                                disabled={feedbackSubmitted[msgIdx] !== undefined}
                                style={{display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', fontSize: '11px', backgroundColor: 'transparent', border: `1px solid ${feedbackSubmitted[msgIdx] === '👍' ? '#22c55e' : 'rgba(148, 163, 184, 0.15)'}`, borderRadius: '4px', cursor: feedbackSubmitted[msgIdx] ? 'default' : 'pointer', color: feedbackSubmitted[msgIdx] === '👍' ? '#22c55e' : '#94a3b8', fontWeight: '500', transition: 'all 0.2s'}}
                                title="This response was helpful"
                              >
                                👍
                              </button>
                              
                              <button
                                onClick={() => handleFeedback(msgIdx, false)}
                                disabled={feedbackSubmitted[msgIdx] !== undefined}
                                style={{display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', fontSize: '11px', backgroundColor: 'transparent', border: `1px solid ${feedbackSubmitted[msgIdx] === '👎' ? '#ef4444' : 'rgba(148, 163, 184, 0.15)'}`, borderRadius: '4px', cursor: feedbackSubmitted[msgIdx] ? 'default' : 'pointer', color: feedbackSubmitted[msgIdx] === '👎' ? '#ef4444' : '#94a3b8', fontWeight: '500', transition: 'all 0.2s'}}
                                title="This response was confusing"
                              >
                                👎
                              </button>
                            </div>
                          </div>
                        ) : (
                          // STRUCTURED SECTIONS (fallback for legacy responses with headers)
                          <div>
                            {sections && sections.length > 0 && sections[0].type !== 'raw' && (
                              <>
                                {sections.map((section, secIdx) => {
                                  const isExpanded = !section.expandable || expandedSections[`${msgIdx}-${secIdx}`] !== false
                                  const isOptional = section.isOptional

                                  return (
                                    <div key={secIdx} style={{borderBottom: 'none', marginBottom: secIdx < sections.length - 1 ? '8px' : '0'}}>
                                      <div
                                        onClick={() => section.expandable && toggleSection(msgIdx, secIdx)}
                                        style={{
                                          padding: '10px 14px',
                                          backgroundColor: 'transparent',
                                          borderLeft: `2px solid ${isOptional ? '#a855f7' : section.type === 'explanation' ? colors.explanationBorder : section.type === 'example' ? colors.exampleBorder : section.type === 'question' ? colors.questionBorder : colors.border}`,
                                          display: 'flex',
                                          justifyContent: 'space-between',
                                          alignItems: 'center',
                                          cursor: section.expandable ? 'pointer' : 'default',
                                          transition: 'background-color 0.2s',
                                        }}
                                        onMouseEnter={(e) => section.expandable && (e.target.style.opacity = '0.8')}
                                        onMouseLeave={(e) => section.expandable && (e.target.style.opacity = '1')}
                                      >
                                        <div style={{display: 'flex', alignItems: 'center', gap: '10px', flex: 1}}>
                                          <span style={{fontSize: '16px'}}>{section.icon}</span>
                                          <span style={{fontWeight: 'bold', fontSize: '13px', color: colors.text}}>{section.title}</span>
                                        </div>
                                        {section.expandable && (
                                          <span style={{fontSize: '14px', color: colors.textMuted}}>
                                            {isExpanded ? '▼' : '▶'}
                                          </span>
                                        )}
                                      </div>

                                      {isExpanded && (
                                        <div style={{padding: '10px 14px', fontSize: `${fontSize}px`, lineHeight: '1.6', color: colors.text, backgroundColor: 'transparent'}}>
                                          <p style={{margin: '0', whiteSpace: 'pre-wrap', wordWrap: 'break-word'}}>{section.content}</p>
                                          
                                          {textToSpeechEnabled && (
                                            <button
                                              onClick={() => handleTextToSpeech(section.content)}
                                              disabled={isSpeaking}
                                              style={{marginTop: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 12px', fontSize: '12px', backgroundColor: colors.accent, border: 'none', borderRadius: '6px', cursor: isSpeaking ? 'default' : 'pointer', color: '#ffffff', fontWeight: 'bold'}}
                                            >
                                              {isSpeaking ? '⏸ Speaking...' : '🔊 Listen'}
                                            </button>
                                          )}
                                        </div>
                                      )}

                                      {!isExpanded && section.expandable && (
                                        <div style={{padding: '8px 14px', fontSize: '12px', color: colors.textMuted, cursor: 'pointer'}}>
                                          <span style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1}}>
                                            {section.content.split('\n')[0].substring(0, 60)}...
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  )
                                })}
                              </>
                            )}
                          </div>
                        )}
                      </div>


                    </div>
                  </div>
                )
              })}
            </>
          )}

          {/* LOADING INDICATOR */}
          {loading && (
            <div style={{display: 'flex', gap: '12px', alignItems: 'flex-start'}}>
              <div style={{fontSize: '28px', marginTop: '4px', flexShrink: 0}}>🤖</div>
              <div style={{display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: colors.bgSecondary, border: '1px solid rgba(148,163,184,0.06)', padding: '12px 16px', borderRadius: '12px', boxShadow: '0 6px 18px rgba(2,6,23,0.06)'}}>
                <span style={{width: '8px', height: '8px', borderRadius: '50%', backgroundColor: colors.accent, animation: 'pulse 1.4s infinite'}}></span>
                <span style={{width: '8px', height: '8px', borderRadius: '50%', backgroundColor: colors.accent, animation: 'pulse 1.4s infinite', animationDelay: '0.2s'}}></span>
                <span style={{width: '8px', height: '8px', borderRadius: '50%', backgroundColor: colors.accent, animation: 'pulse 1.4s infinite', animationDelay: '0.4s'}}></span>
              </div>
            </div>
          )}

        </div>

        {/* INPUT AREA */}
        <div style={{backgroundColor: 'transparent', borderTop: '1px solid rgba(148, 163, 184, 0.08)', padding: '8px 12px', margin: '0 auto', width: '100%', boxSizing: 'border-box'}}>
          <div style={{display: 'flex', flexDirection: 'column', gap: '6px'}}>
            {/* QUICK ACTIONS - GROUPED */}
            <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center'}}>
              {getContextualActions().map((action, idx) => {
                const isPrimary = idx < 3
                const accent = isPrimary ? '#60a5fa' : '#86efac'
                return (
                  <button
                    key={idx}
                    onClick={() => handleQuickResponse(action)}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: 'transparent',
                      color: accent,
                      border: '1px solid rgba(148, 163, 184, 0.12)',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: '500',
                      letterSpacing: '0px',
                      transition: 'all 0.2s ease',
                      boxShadow: 'none'
                    }}
                    title={`Send: "${action}"`}
                    aria-label={`Learning action: ${action}`}
                  >
                    {action}
                  </button>
                )
              })}
            </div>

            {/* INPUT WITH SEND AND MICROPHONE */}
            <div style={{display: 'flex', gap: '6px', alignItems: 'center', paddingTop: '4px', borderTop: `1px solid rgba(148, 163, 184, 0.08)`, flexWrap: 'wrap'}}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message..."
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  backgroundColor: 'rgba(100, 116, 139, 0.05)',
                  border: '1px solid rgba(148, 163, 184, 0.1)',
                  borderRadius: '6px',
                  color: colors.text,
                  fontSize: '13px',
                  fontFamily: 'inherit',
                  resize: 'none',
                  maxHeight: '90px',
                  minHeight: '38px',
                  outline: 'none',
                  boxShadow: 'none'
                }}
                rows="1"
                disabled={loading}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' && !e.shiftKey) || (e.key === 'Enter' && e.ctrlKey)) {
                    if (!loading && input.trim()) {
                      e.preventDefault()
                      handleSubmit()
                    }
                  }
                }}
                aria-label="Chat input"
              />

<div style={{display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap'}}>
              <button
                onClick={isListening ? stopSpeechInput : startSpeechInput}
                disabled={loading}
                style={{
                  padding: '6px 8px',
                  backgroundColor: 'transparent',
                  color: isListening ? '#ef4444' : '#60a5fa',
                  border: `1px solid ${isListening ? 'rgba(239, 68, 68, 0.3)' : 'rgba(96, 165, 250, 0.3)'}`,
                  borderRadius: '4px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: '500',
                  fontSize: '13px',
                  transition: 'all 0.2s ease',
                  opacity: loading ? 0.55 : 1,
                  whiteSpace: 'nowrap',
                  boxShadow: 'none'
                }}
                title={isListening ? 'Stop listening (or press Escape)' : 'Start voice input'}
              >
                {isListening ? '◻' : '🎤'}
              </button>

              <button
                onClick={handleSubmit}
                disabled={!input.trim() || loading}
                style={{
                  padding: '6px 10px',
                  backgroundColor: !input.trim() || loading ? 'transparent' : 'rgba(34, 197, 94, 0.2)',
                  color: !input.trim() || loading ? '#64748b' : '#22c55e',
                  border: `1px solid ${!input.trim() || loading ? 'rgba(148, 163, 184, 0.12)' : 'rgba(34, 197, 94, 0.3)'}`,
                  borderRadius: '4px',
                  cursor: !input.trim() || loading ? 'not-allowed' : 'pointer',
                  fontWeight: '500',
                  fontSize: '13px',
                  transition: 'all 0.2s ease',
                  opacity: !input.trim() || loading ? 0.55 : 1,
                  whiteSpace: 'nowrap',
                  boxShadow: 'none'
                  }}
                  title={loading ? 'Waiting for response...' : 'Send message (Enter)'}
                >
                  {loading ? '...' : '→'}
                </button>
              </div>

              {speechError && (
                <div style={{
                  fontSize: '11px',
                  color: '#ef4444',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  textAlign: 'right'
                }}>
                  {speechError}
                </div>
              )}
            </div>

            <div style={{fontSize: '10px', color: colors.textMuted, textAlign: 'center', opacity: 0.6, lineHeight: 1.3, marginTop: '3px', marginBottom: '0px'}}>
              Enter to submit, Shift+Enter for new lines
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const styleSheet = document.createElement('style')
styleSheet.textContent = `
  @keyframes pulse {
    0%, 60%, 100% { opacity: 0.3; }
    30% { opacity: 1; }
  }
  
  @keyframes speak {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
  }
  
  @keyframes wavebar {
    0%, 100% { height: 4px; }
    50% { height: 12px; }
  }
`
document.head.appendChild(styleSheet)

export default Learning
