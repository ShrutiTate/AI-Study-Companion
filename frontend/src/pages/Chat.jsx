import { useState, useEffect } from 'react'
import { FriendChatProvider, useFriendChat } from '../contexts/FriendChatContext'
import { FriendChatWindow } from '../components/FriendChatWindow'

// Inner component that uses the Friend Chat context
function ChatContent() {
  const [friendIdInput, setFriendIdInput] = useState('')
  const [selectedFriend, setSelectedFriend] = useState(null)
  const [error, setError] = useState('')
  
  const { userId } = useFriendChat()

  const handleStartChat = () => {
    if (!friendIdInput.trim()) {
      setError('Please enter a friend ID')
      return
    }
    setSelectedFriend(friendIdInput)
    setError('')
  }

  const handleBackToSelection = () => {
    setSelectedFriend(null)
    setFriendIdInput('')
    setError('')
  }

  // Chat Window View
  if (selectedFriend) {
    return (
      <FriendChatWindow 
        userId={userId}
        friendId={selectedFriend} 
        onClose={handleBackToSelection} 
      />
    )
  }

  // Friend Selection View
  return (
    <div style={styles.container}>
      <div style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>👥 Friend Chat</h1>
          <p style={styles.subtitle}>Connect & chat with friends in real-time</p>
        </div>

        {error && (
          <div style={styles.errorBanner}>
            ⚠️ {error}
          </div>
        )}

        <div style={styles.card}>
          <label style={styles.label}>Friend ID</label>
          <input
            type="text"
            placeholder="Enter friend's ID (e.g., 'bob', 'alice')..."
            value={friendIdInput}
            onChange={(e) => setFriendIdInput(e.target.value)}
            style={styles.input}
            onKeyPress={(e) => e.key === 'Enter' && handleStartChat()}
          />

          <button 
            onClick={handleStartChat}
            style={styles.button}
            disabled={!friendIdInput.trim()}
          >
            Start Chat
          </button>

          <div style={styles.tipBox}>
            <p style={styles.tipText}>
              💡 <strong>Tip:</strong> You'll see real-time translation of all messages. Messages are synced across tabs in real-time.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Outer wrapper component with FriendChatProvider
function Chat() {
  const [userId, setUserId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Try to get user_id from localStorage (set after login)
    const storedUserId = localStorage.getItem('user_id')
    
    if (storedUserId) {
      setUserId(storedUserId)
      setLoading(false)
    } else {
      // User not logged in - show error
      setError('Please log in first to use Friend Chat')
      setLoading(false)
    }
  }, [])

  if (loading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'rgb(11, 18, 32)',
        color: 'white'
      }}>
        <p>Loading...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'rgb(11, 18, 32)',
        color: 'white'
      }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: '#ff6b6b', fontSize: '16px' }}>❌ {error}</p>
          <a href="/login" style={{ 
            marginTop: '20px', 
            color: '#4ecdc4', 
            textDecoration: 'none' 
          }}>
            Go to Login
          </a>
        </div>
      </div>
    )
  }

  return userId ? (
    <FriendChatProvider userId={userId}>
      <ChatContent />
    </FriendChatProvider>
  ) : null
}

const styles = {
  container: {
    minHeight: '100vh',
    background: 'rgb(11, 18, 32)',
    color: 'white',
    fontFamily: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
    padding: '20px',
  },
  main: {
    maxWidth: '600px',
    margin: '0 auto',
    paddingTop: '40px',
  },
  header: {
    marginBottom: '40px',
    textAlign: 'center',
  },
  title: {
    margin: '0 0 12px 0',
    fontSize: '36px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  subtitle: {
    margin: '0',
    color: '#94a3b8',
    fontSize: '16px',
  },
  card: {
    background: 'rgba(15, 23, 42, 0.9)',
    padding: '24px',
    borderRadius: '12px',
    border: '1px solid rgba(148, 163, 184, 0.06)',
    boxShadow: 'rgba(2, 6, 23, 0.06) 0px 8px 24px',
    marginBottom: '18px',
  },
  label: {
    display: 'block',
    marginBottom: '12px',
    fontSize: '14px',
    fontWeight: '600',
    color: '#cbd5e1',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  input: {
    width: '100%',
    padding: '12px',
    marginBottom: '16px',
    borderRadius: '10px',
    border: '1px solid rgba(148, 163, 184, 0.06)',
    backgroundColor: '#0f172a',
    color: 'white',
    fontSize: '14px',
    boxSizing: 'border-box',
    transition: 'all 0.3s ease',
  },
  button: {
    width: '100%',
    padding: '14px',
    background: 'rgba(37, 99, 235, 0.12)',
    border: '1px solid rgba(37, 99, 235, 0.12)',
    borderRadius: '10px',
    color: 'white',
    fontWeight: '600',
    cursor: 'pointer',
    fontSize: '16px',
    transition: 'all 0.25s ease',
    boxShadow: 'rgba(37, 99, 235, 0.3) 0px 5px 15px',
    marginBottom: '16px',
  },
  tipBox: {
    background: 'rgba(59, 130, 246, 0.1)',
    border: '1px solid rgba(59, 130, 246, 0.3)',
    borderRadius: '8px',
    padding: '12px',
    marginTop: '16px',
  },
  tipText: {
    margin: '0',
    fontSize: '13px',
    color: '#cbd5e1',
    lineHeight: '1.5',
  },
  errorBanner: {
    background: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '8px',
    padding: '12px',
    marginBottom: '16px',
    color: '#fca5a5',
    fontSize: '14px',
  },
}

export default Chat
