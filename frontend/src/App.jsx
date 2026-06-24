import { BrowserRouter, Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import './App.css'
import Learning from './pages/Learning'
import Analytics from './pages/Analytics'
import History from './pages/History'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import FriendChat from './pages/FriendChat'
import { FriendChatProvider } from './contexts/FriendChatContext'
import { FriendSystemProvider, useFriendSystem } from './contexts/FriendSystemContext'

function NotificationBell() {
  const { pendingRequests } = useFriendSystem();
  return (
    <div className="notification-bell" style={{ display: 'inline-block', marginLeft: '5px' }}>
      {pendingRequests?.length > 0 && <span className="bell-badge">🔔({pendingRequests.length})</span>}
    </div>
  );
}

function AppContent() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [userName, setUserName] = useState('')
  const [userId, setUserId] = useState('')
  const location = useLocation()

  useEffect(() => {
    const uid = localStorage.getItem('user_id')
    const name = localStorage.getItem('name')
    if (uid) {
      setIsLoggedIn(true)
      setUserId(uid)
      setUserName(name)
    } else {
      setIsLoggedIn(false)
      setUserId('')
      setUserName('')
    }
  }, [location])

  const handleLogout = () => {
    localStorage.removeItem('user_id')
    localStorage.removeItem('name')
    localStorage.removeItem('email')
    setIsLoggedIn(false)
    setUserId('')
    setUserName('')
  }

  const MainApp = () => (
    <>
      <nav className="app-nav" aria-label="Primary navigation">
        <div className="nav-content">
          <h2 className="logo">EchoConnect</h2>
          <div className="nav-links">
            <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Dashboard</NavLink>
            <NavLink to="/learning" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Learning</NavLink>
            <NavLink to="/friend-chat" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Friends<NotificationBell />
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>History</NavLink>
            <NavLink to="/analytics" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Analytics</NavLink>
            <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Settings</NavLink>
            <button type="button" className="logout-button" onClick={handleLogout}>Logout</button>
          </div>
        </div>
      </nav>

      <div className="routes-wrapper">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/learning" element={<Learning />} />
          <Route path="/history" element={<History />} />
          <Route path="/friend-chat" element={<FriendChat />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/" element={<Dashboard />} />
        </Routes>
      </div>
    </>
  );

  return (
    <div className="app-wrapper">
      {isLoggedIn && userId ? (
        <FriendChatProvider userId={userId}>
          <FriendSystemProvider currentUserId={userId}>
            <MainApp />
          </FriendSystemProvider>
        </FriendChatProvider>
      ) : (
        <div className="routes-wrapper">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<Login />} />
          </Routes>
        </div>
      )}
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}

export default App
