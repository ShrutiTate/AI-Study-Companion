import { useState, useEffect } from 'react'

function SessionQuiz({ sessionId, onClose, theme = 'dark' }) {
  const [questions, setQuestions] = useState([])
  const [currentQuestion, setCurrentQuestion] = useState(0)
  const [answers, setAnswers] = useState({})
  const [loading, setLoading] = useState(true)
  const [quizComplete, setQuizComplete] = useState(false)
  const [score, setScore] = useState(0)
  const [submitted, setSubmitted] = useState(false)

  const getThemeColors = () => {
    const themes = {
      dark: {
        bg: '#0f172a',
        bgSecondary: '#1e293b',
        text: '#e2e8f0',
        textMuted: '#94a3b8',
        border: '#334155',
        accent: '#06b6d4',
        success: '#22c55e',
        error: '#ef4444',
        warning: '#f59e0b'
      },
      light: {
        bg: '#f8fafc',
        bgSecondary: '#f1f5f9',
        text: '#0f172a',
        textMuted: '#64748b',
        border: '#cbd5e1',
        accent: '#0284c7',
        success: '#16a34a',
        error: '#dc2626',
        warning: '#d97706'
      }
    }
    return themes[theme] || themes.dark
  }

  const colors = getThemeColors()

  // Generate quiz on mount
  useEffect(() => {
    generateQuiz()
  }, [sessionId])

  const generateQuiz = async () => {
    setLoading(true)
    try {
      const response = await fetch('/quiz/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, num_questions: 9 })
      })
      
      const data = await response.json()
      
      if (data.success && data.data && data.data.questions) {
        setQuestions(data.data.questions)
        setAnswers({})
        setCurrentQuestion(0)
        setQuizComplete(false)
        setSubmitted(false)
        console.log('[QUIZ] Generated', data.data.questions.length, 'questions')
      } else {
        console.error('[QUIZ] Failed to generate quiz:', data.error)
        alert('Failed to generate quiz: ' + (data.error || 'Unknown error'))
      }
    } catch (error) {
      console.error('[QUIZ] Error:', error)
      alert('Error generating quiz: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectOption = (option) => {
    if (!submitted) {
      setAnswers({
        ...answers,
        [currentQuestion]: option
      })
    }
  }

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1)
    } else {
      submitQuiz()
    }
  }

  const handlePrevious = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(currentQuestion - 1)
    }
  }

  const submitQuiz = () => {
    // Calculate score
    let correctCount = 0
    questions.forEach((q, idx) => {
      if (answers[idx] === q.answer) {
        correctCount++
      }
    })
    
    setScore(Math.round((correctCount / questions.length) * 100))
    setQuizComplete(true)
    setSubmitted(true)
  }

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: colors.bg
      }}>
        <div style={{textAlign: 'center'}}>
          <div style={{fontSize: '48px', marginBottom: '16px'}}>🎯</div>
          <p style={{color: colors.text, fontSize: '18px', fontWeight: 'bold'}}>Generating your adaptive quiz...</p>
          <p style={{color: colors.textMuted, fontSize: '14px', marginTop: '8px'}}>Based on your session data</p>
        </div>
      </div>
    )
  }

  if (quizComplete && submitted) {
    const performanceLevel = score >= 80 ? '⭐ Excellent!' : score >= 60 ? '👍 Good Job!' : '📚 Keep Learning!'
    const performanceColor = score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444'
    
    return (
      <div style={{
        minHeight: '100vh',
        backgroundColor: colors.bg,
        color: colors.text,
        padding: '40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{maxWidth: '600px', width: '100%', textAlign: 'center'}}>
          <div style={{fontSize: '72px', marginBottom: '24px'}}>🎉</div>
          <h1 style={{fontSize: '42px', fontWeight: 'bold', marginBottom: '16px', color: colors.accent}}>Quiz Complete!</h1>
          
          {/* Score */}
          <div style={{
            backgroundColor: colors.bgSecondary,
            border: `2px solid ${performanceColor}`,
            borderRadius: '16px',
            padding: '40px',
            marginBottom: '32px'
          }}>
            <div style={{fontSize: '64px', fontWeight: 'bold', color: performanceColor, marginBottom: '12px'}}>
              {score}%
            </div>
            <div style={{fontSize: '24px', fontWeight: 'bold', color: performanceColor, marginBottom: '16px'}}>
              {performanceLevel}
            </div>
            <p style={{color: colors.textMuted, fontSize: '14px'}}>
              You got {Object.keys(answers).filter(idx => answers[idx] === questions[idx]?.answer).length} out of {questions.length} questions correct
            </p>
          </div>

          {/* Breakdown */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '12px',
            marginBottom: '32px'
          }}>
            {['easy', 'medium', 'hard'].map(difficulty => {
              const qsOfDiff = questions.filter(q => q.difficulty === difficulty)
              const correctOfDiff = qsOfDiff.filter((q, idx) => {
                const qIdx = questions.indexOf(q)
                return answers[qIdx] === q.answer
              }).length
              
              return (
                <div key={difficulty} style={{
                  backgroundColor: colors.bgSecondary,
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px',
                  padding: '16px'
                }}>
                  <div style={{fontSize: '12px', color: colors.textMuted, textTransform: 'capitalize', marginBottom: '8px'}}>
                    {difficulty}
                  </div>
                  <div style={{fontSize: '24px', fontWeight: 'bold', color: colors.accent}}>
                    {correctOfDiff}/{qsOfDiff.length}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Action Buttons */}
          <div style={{display: 'flex', gap: '12px', justifyContent: 'center'}}>
            <button
              onClick={() => {
                setCurrentQuestion(0)
                setAnswers({})
                setQuizComplete(false)
                setSubmitted(false)
                generateQuiz()
              }}
              style={{
                padding: '12px 24px',
                backgroundColor: colors.accent,
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                transition: 'opacity 0.3s'
              }}
              onMouseEnter={(e) => e.target.style.opacity = '0.9'}
              onMouseLeave={(e) => e.target.style.opacity = '1'}
            >
              🔄 Retake Quiz
            </button>
            <button
              onClick={onClose}
              style={{
                padding: '12px 24px',
                backgroundColor: colors.bgSecondary,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                transition: 'opacity 0.3s'
              }}
              onMouseEnter={(e) => e.target.style.opacity = '0.9'}
              onMouseLeave={(e) => e.target.style.opacity = '1'}
            >
              ← Back
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!questions || questions.length === 0) {
    return (
      <div style={{
        minHeight: '100vh',
        backgroundColor: colors.bg,
        color: colors.text,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{textAlign: 'center'}}>
          <div style={{fontSize: '48px', marginBottom: '16px'}}>⚠️</div>
          <p style={{color: colors.text, fontSize: '18px'}}>No quiz questions available</p>
        </div>
      </div>
    )
  }

  const question = questions[currentQuestion]
  const selectedOption = answers[currentQuestion]
  const progress = Math.round(((currentQuestion + 1) / questions.length) * 100)

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: colors.bg,
      color: colors.text,
      padding: '40px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <div style={{maxWidth: '700px', width: '100%'}}>
        {/* Header */}
        <div style={{marginBottom: '32px'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px'}}>
            <h1 style={{fontSize: '28px', fontWeight: 'bold', margin: '0', color: colors.accent}}>📝 Quiz</h1>
            <span style={{color: colors.textMuted, fontSize: '14px'}}>
              Question {currentQuestion + 1} of {questions.length}
            </span>
          </div>
          
          {/* Progress Bar */}
          <div style={{
            height: '6px',
            backgroundColor: colors.border,
            borderRadius: '3px',
            overflow: 'hidden'
          }}>
            <div style={{
              height: '100%',
              backgroundColor: colors.accent,
              width: `${progress}%`,
              transition: 'width 0.3s'
            }} />
          </div>
        </div>

        {/* Question */}
        <div style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: '12px',
          padding: '32px',
          marginBottom: '24px'
        }}>
          <div style={{marginBottom: '8px', fontSize: '12px', color: colors.textMuted, textTransform: 'uppercase', fontWeight: '600'}}>
            Difficulty: {question.difficulty}
          </div>
          <h2 style={{fontSize: '22px', fontWeight: 'bold', margin: '0 0 12px 0', lineHeight: '1.5', color: colors.text}}>
            {question.question}
          </h2>
          <p style={{fontSize: '12px', color: colors.textMuted, margin: '0'}}>
            Topic: {question.concept}
          </p>
        </div>

        {/* Options */}
        <div style={{marginBottom: '32px', display: 'flex', flexDirection: 'column', gap: '12px'}}>
          {question.options.map((option, idx) => {
            const isSelected = selectedOption === option
            const isCorrect = option === question.answer
            const showResult = submitted && isSelected && isCorrect
            const showIncorrect = submitted && isSelected && !isCorrect
            const showCorrectUnselected = submitted && !isSelected && isCorrect
            
            let bgColor = colors.bgSecondary
            let borderColor = colors.border
            let textColor = colors.text
            
            if (showResult) {
              bgColor = '#dcfce7'
              borderColor = colors.success
              textColor = '#166534'
            } else if (showIncorrect) {
              bgColor = '#fee2e2'
              borderColor = colors.error
              textColor = '#7f1d1d'
            } else if (showCorrectUnselected) {
              bgColor = '#dcfce7'
              borderColor = colors.success
              textColor = '#166534'
            } else if (isSelected && !submitted) {
              bgColor = colors.accent
              borderColor = colors.accent
              textColor = '#ffffff'
            }
            
            return (
              <button
                key={idx}
                onClick={() => handleSelectOption(option)}
                disabled={submitted}
                style={{
                  padding: '16px',
                  backgroundColor: bgColor,
                  color: textColor,
                  border: `2px solid ${borderColor}`,
                  borderRadius: '8px',
                  cursor: submitted ? 'default' : 'pointer',
                  fontWeight: '500',
                  fontSize: '15px',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                  opacity: submitted && !isSelected && !showCorrectUnselected ? '0.6' : '1'
                }}
                onMouseEnter={(e) => !submitted && (e.target.style.borderColor = colors.accent)}
                onMouseLeave={(e) => !submitted && (e.target.style.borderColor = borderColor)}
              >
                <span style={{marginRight: '12px', fontWeight: 'bold'}}>
                  {String.fromCharCode(65 + idx)}.
                </span>
                {option}
                {submitted && showResult && ' ✓'}
                {submitted && showIncorrect && ' ✗'}
                {submitted && showCorrectUnselected && ' (Correct Answer)'}
              </button>
            )
          })}
        </div>

        {/* Navigation */}
        <div style={{display: 'flex', gap: '12px', justifyContent: 'space-between'}}>
          <button
            onClick={handlePrevious}
            disabled={currentQuestion === 0}
            style={{
              padding: '12px 24px',
              backgroundColor: colors.bgSecondary,
              color: currentQuestion === 0 ? colors.textMuted : colors.text,
              border: `1px solid ${colors.border}`,
              borderRadius: '8px',
              cursor: currentQuestion === 0 ? 'not-allowed' : 'pointer',
              fontWeight: '600',
              opacity: currentQuestion === 0 ? '0.5' : '1'
            }}
          >
            ← Previous
          </button>

          <button
            onClick={handleNext}
            disabled={!selectedOption && !submitted}
            style={{
              padding: '12px 32px',
              backgroundColor: colors.accent,
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              cursor: !selectedOption && !submitted ? 'not-allowed' : 'pointer',
              fontWeight: '600',
              opacity: !selectedOption && !submitted ? '0.5' : '1',
              transition: 'opacity 0.2s'
            }}
            onMouseEnter={(e) => !selectedOption && !submitted || (e.target.style.opacity = '0.9')}
            onMouseLeave={(e) => !selectedOption && !submitted || (e.target.style.opacity = '1')}
          >
            {currentQuestion === questions.length - 1 ? submitted ? '✓ Submitted' : 'Submit Quiz' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SessionQuiz
