import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Login() {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const endpoint = isLogin ? '/login' : '/register'
      const body = isLogin 
        ? { email, password }
        : { name, email, password }

      const response = await fetch(`/api/auth${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      // Parse response with error handling
      const text = await response.text()
      if (!text) {
        throw new Error("Empty response from server")
      }
      
      let data
      try {
        data = JSON.parse(text)
      } catch(e) {
        console.error('[LOGIN] JSON parse failed. Raw response:', text)
        throw new Error(`Invalid JSON from server: ${text.substring(0, 200)}`)
      }

      if (data.error) {
        setError(data.error)
        setLoading(false)
        return
      }

      // Store user info
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('name', data.name)
      localStorage.setItem('email', data.email)
      
      console.log('[LOGIN] User logged in successfully')
      console.log('[LOGIN] Stored user_id:', data.user_id)
      console.log('[LOGIN] Stored name:', data.name)
      console.log('[LOGIN] Stored email:', data.email)

      // Redirect to dashboard
      navigate('/dashboard')
    } catch (err) {
      setError('Connection error: ' + err.message)
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>🚀 EchoConnect</h1>
        <p style={styles.subtitle}>{isLogin ? 'Welcome Back' : 'Join Us'}</p>

        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <input
              type="text"
              placeholder="Full Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={styles.input}
              required
            />
          )}

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={styles.input}
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
            required
          />

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? 'Loading...' : isLogin ? 'Login' : 'Register'}
          </button>
        </form>

        <p style={styles.toggle}>
          {isLogin ? "Don't have an account? " : 'Already have an account? '}
          <button
            onClick={() => {
              setIsLogin(!isLogin)
              setError('')
            }}
            style={styles.toggleButton}
          >
            {isLogin ? 'Register' : 'Login'}
          </button>
        </p>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    background: 'linear-gradient(135deg, #0f172a, #1e293b)',
    color: 'white',
    padding: '20px',
  },
  card: {
    background: '#1e293b',
    padding: '40px',
    borderRadius: '12px',
    width: '100%',
    maxWidth: '400px',
    boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
    border: '1px solid rgba(255,255,255,0.1)',
  },
  title: {
    margin: '0 0 10px 0',
    fontSize: '32px',
    fontWeight: '700',
    textAlign: 'center',
  },
  subtitle: {
    margin: '0 0 30px 0',
    fontSize: '16px',
    color: '#94a3b8',
    textAlign: 'center',
  },
  input: {
    width: '100%',
    padding: '12px',
    marginBottom: '15px',
    background: '#0f172a',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '8px',
    color: 'white',
    fontSize: '14px',
    boxSizing: 'border-box',
  },
  button: {
    width: '100%',
    padding: '12px',
    background: '#3b82f6',
    border: 'none',
    borderRadius: '8px',
    color: 'white',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    marginTop: '10px',
  },
  error: {
    color: '#ef4444',
    marginBottom: '15px',
    fontSize: '14px',
    textAlign: 'center',
  },
  toggle: {
    marginTop: '20px',
    textAlign: 'center',
    color: '#94a3b8',
    fontSize: '14px',
  },
  toggleButton: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '600',
    padding: '0',
  },
}

export default Login
