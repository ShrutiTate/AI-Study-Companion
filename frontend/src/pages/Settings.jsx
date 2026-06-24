import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Settings() {
  const [user, setUser] = useState({ name: '', email: '' })
  const [materials, setMaterials] = useState([])
  const [materialsLoading, setMaterialsLoading] = useState(false)
  const [uploadTopic, setUploadTopic] = useState('')
  const [uploadContent, setUploadContent] = useState('')
  const [selectedPdfFile, setSelectedPdfFile] = useState(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [notification, setNotification] = useState(null)
  
  const navigate = useNavigate()
  const userId = localStorage.getItem('user_id') || 'guest_user'

  useEffect(() => {
    const name = localStorage.getItem('name') || 'Guest'
    const email = localStorage.getItem('email') || 'guest@example.com'
    setUser({ name, email })
    fetchStudyMaterials()
  }, [])

  const fetchStudyMaterials = async () => {
    if (!userId) return
    setMaterialsLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/learning/study-materials/${userId}`)
      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          setMaterials(data.materials || [])
        }
      }
    } catch (error) {
      console.error('Error fetching study materials:', error)
    } finally {
      setMaterialsLoading(false)
    }
  }

  const showNotification = (text, type = 'success') => {
    setNotification({ text, type })
    setTimeout(() => {
      setNotification(null)
    }, 4000)
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!uploadTopic.trim()) {
      showNotification('Topic cannot be empty', 'error')
      return
    }
    if (!uploadContent.trim() && !selectedPdfFile) {
      showNotification('Please provide notes text or select a PDF', 'error')
      return
    }

    if (selectedPdfFile && selectedPdfFile.type !== 'application/pdf') {
      showNotification('Only PDF files are supported for PDF upload', 'error')
      return
    }

    setUploadLoading(true)
    try {
      let response
      if (selectedPdfFile) {
        const formData = new FormData()
        formData.append('user_id', userId)
        formData.append('topic', uploadTopic.trim())
        formData.append('file', selectedPdfFile)

        response = await fetch('http://localhost:8000/learning/upload-pdf-notes', {
          method: 'POST',
          body: formData,
        })
      } else {
        response = await fetch('http://localhost:8000/learning/upload-content', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: userId,
            topic: uploadTopic.trim(),
            content: uploadContent.trim(),
          }),
        })
      }

      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          if (selectedPdfFile) {
            showNotification(`PDF uploaded for future RAG retrieval: ${data.pdf_file_name || selectedPdfFile.name}`)
          } else {
            showNotification(`Successfully chunked into ${data.chunk_count} blocks!`)
          }
          setUploadTopic('')
          setUploadContent('')
          setSelectedPdfFile(null)
          fetchStudyMaterials()
        } else {
          showNotification(data.error || 'Failed to upload study material', 'error')
        }
      } else {
        showNotification('Failed to upload study material', 'error')
      }
    } catch (error) {
      showNotification('Server connection failed', 'error')
      console.error(error)
    } finally {
      setUploadLoading(false)
    }
  }

  const handlePdfChange = (e) => {
    const file = e.target.files?.[0] || null
    if (file && file.type !== 'application/pdf') {
      setSelectedPdfFile(null)
      showNotification('Only PDF files are supported', 'error')
      return
    }

    setSelectedPdfFile(file)
  }

  const handleDelete = async (topic) => {
    if (!window.confirm(`Are you sure you want to delete materials for '${topic}'?`)) {
      return
    }

    try {
      const response = await fetch(`http://localhost:8000/learning/delete-content/${userId}/${encodeURIComponent(topic)}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        showNotification(`Deleted study material for '${topic}' successfully!`)
        fetchStudyMaterials()
      } else {
        showNotification('Failed to delete study material', 'error')
      }
    } catch (error) {
      showNotification('Server connection failed', 'error')
      console.error(error)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('user_id')
    localStorage.removeItem('name')
    localStorage.removeItem('email')
    navigate('/login')
  }

  const styles = {
    container: {
      minHeight: '100vh',
      width: '100%',
      background: '#0b1220',
      color: 'white',
      fontFamily: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
      padding: '24px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-start',
    },
    card: {
      width: '100%',
      maxWidth: '1100px',
      background: '#0f172a',
      borderRadius: '24px',
      padding: '36px',
      boxShadow: '0 24px 70px rgba(0, 0, 0, 0.28)',
      display: 'flex',
      flexDirection: 'column',
      gap: '30px',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      gap: '20px',
      flexWrap: 'wrap',
      alignItems: 'flex-start',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      paddingBottom: '24px',
    },
    titleGroup: {
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
    },
    title: {
      margin: 0,
      fontSize: '32px',
      fontWeight: '800',
      color: 'white',
    },
    subtitle: {
      margin: 0,
      color: '#94a3b8',
      fontSize: '16px',
      lineHeight: 1.6,
    },
    profileBox: {
      background: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(148, 163, 184, 0.12)',
      borderRadius: '20px',
      padding: '24px',
      minWidth: '240px',
    },
    profileName: {
      margin: 0,
      fontSize: '22px',
      fontWeight: '700',
      color: 'white',
    },
    profileEmail: {
      margin: '6px 0 0 0',
      color: '#94a3b8',
      fontSize: '14px',
    },
    sectionGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
      gap: '20px',
    },
    sectionCard: {
      background: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(148, 163, 184, 0.12)',
      borderRadius: '20px',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
    },
    studyCard: {
      background: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(59, 130, 246, 0.25)',
      borderRadius: '20px',
      padding: '28px',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      boxShadow: '0 8px 32px rgba(59, 130, 246, 0.05)',
    },
    studyGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
      gap: '24px',
    },
    sectionTitle: {
      margin: 0,
      fontSize: '18px',
      fontWeight: '700',
      color: 'white',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    },
    sectionText: {
      margin: 0,
      color: '#94a3b8',
      lineHeight: 1.7,
      fontSize: '14px',
    },
    button: {
      padding: '12px 18px',
      borderRadius: '12px',
      border: '1px solid rgba(59, 130, 246, 0.3)',
      background: 'rgba(59, 130, 246, 0.15)',
      color: 'white',
      fontWeight: '700',
      cursor: 'pointer',
      alignSelf: 'flex-start',
      transition: 'all 0.25s ease',
    },
    uploadButton: {
      padding: '12px 24px',
      borderRadius: '12px',
      border: 'none',
      background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
      color: 'white',
      fontWeight: '700',
      cursor: 'pointer',
      transition: 'all 0.25s ease',
      boxShadow: '0 4px 14px rgba(59, 130, 246, 0.3)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
    },
    dangerButton: {
      padding: '12px 18px',
      borderRadius: '12px',
      border: '1px solid rgba(248, 113, 113, 0.35)',
      background: 'rgba(239, 68, 68, 0.18)',
      color: 'white',
      fontWeight: '700',
      cursor: 'pointer',
      transition: 'all 0.25s ease',
      marginTop: '10px',
    },
    deleteButton: {
      padding: '8px 14px',
      borderRadius: '8px',
      border: '1px solid rgba(239, 68, 68, 0.25)',
      background: 'rgba(239, 68, 68, 0.1)',
      color: '#ef4444',
      fontWeight: '600',
      cursor: 'pointer',
      fontSize: '13px',
      transition: 'all 0.25s ease',
    },
    input: {
      width: '100%',
      padding: '12px 16px',
      background: '#0b1220',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '12px',
      color: 'white',
      fontSize: '14px',
      outline: 'none',
      transition: 'all 0.25s ease',
    },
    textarea: {
      width: '100%',
      minHeight: '120px',
      padding: '12px 16px',
      background: '#0b1220',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '12px',
      color: 'white',
      fontSize: '14px',
      outline: 'none',
      resize: 'vertical',
      fontFamily: 'inherit',
      transition: 'all 0.25s ease',
    },
    materialList: {
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      maxHeight: '340px',
      overflowY: 'auto',
      paddingRight: '6px',
    },
    materialItem: {
      background: '#0b1220',
      borderRadius: '12px',
      padding: '16px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      border: '1px solid rgba(255, 255, 255, 0.05)',
    },
    materialMeta: {
      marginTop: '4px',
      color: '#94a3b8',
      fontSize: '12px',
      lineHeight: 1.4,
    },
    materialInfo: {
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
    },
    topicName: {
      fontWeight: '600',
      fontSize: '15px',
      margin: 0,
      color: '#e2e8f0',
      textTransform: 'capitalize',
    },
    chunkBadge: {
      fontSize: '12px',
      background: 'rgba(59, 130, 246, 0.2)',
      color: '#60a5fa',
      padding: '2px 8px',
      borderRadius: '20px',
      alignSelf: 'flex-start',
      fontWeight: '600',
    },
    toast: {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      padding: '16px 24px',
      borderRadius: '12px',
      color: 'white',
      fontWeight: '600',
      zIndex: 1000,
      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.25)',
      animation: 'slideIn 0.3s ease',
    },
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.header}>
          <div style={styles.titleGroup}>
            <h1 style={styles.title}>Profile & Settings</h1>
            <p style={styles.subtitle}>Manage your account, study materials, and system configurations.</p>
          </div>
          <div style={styles.profileBox}>
            <h2 style={styles.profileName}>{user.name}</h2>
            <p style={styles.profileEmail}>{user.email}</p>
            <button style={styles.button} onClick={() => window.alert('Profile editing coming soon')}>
              Edit profile
            </button>
          </div>
        </div>

        {/* STUDY MATERIALS SECTION */}
        <div style={styles.studyCard}>
          <h3 style={styles.sectionTitle}>
            <span>📚</span> Study Materials Manager (Additive RAG Data)
          </h3>
          <p style={styles.sectionText}>
            Provide custom reference materials or notes for specific topics. The AI Tutor automatically retrieves relevant sections during active learning to enrich your explanations and align them with your notes.
          </p>

          <div style={styles.studyGrid}>
            {/* Left: Upload Form */}
            <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: '600', color: '#94a3b8' }}>
                  Learning Topic
                </label>
                <input
                  type="text"
                  placeholder="e.g., Python Lists, Neural Networks, Photosynthesis"
                  value={uploadTopic}
                  onChange={(e) => setUploadTopic(e.target.value)}
                  style={styles.input}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: '600', color: '#94a3b8' }}>
                  Upload PDF Notes (future RAG retrieval)
                </label>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handlePdfChange}
                  style={styles.input}
                />
                <p style={{ margin: '8px 0 0 0', color: '#94a3b8', fontSize: '13px', lineHeight: 1.5 }}>
                  Select a PDF file to save as notes for future semantic retrieval. Text upload still works now.
                </p>
                {selectedPdfFile && (
                  <div style={{ marginTop: '10px', color: '#60a5fa', fontSize: '13px' }}>
                    Selected PDF: {selectedPdfFile.name}
                  </div>
                )}
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: '600', color: '#94a3b8' }}>
                  Study Notes / Textbook Content
                </label>
                <textarea
                  placeholder="Paste or type your reference material here. We will split it into clean semantic chunks for exact reference..."
                  value={uploadContent}
                  onChange={(e) => setUploadContent(e.target.value)}
                  style={styles.textarea}
                />
              </div>

              <button type="submit" style={styles.uploadButton} disabled={uploadLoading}>
                {uploadLoading ? (selectedPdfFile ? 'Uploading PDF...' : 'Processing Semantic Chunks...') : 'Upload Reference Notes'}
              </button>
            </form>

            {/* Right: Uploaded List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#94a3b8' }}>
                Your Reference Topics ({materials.length})
              </label>

              {materialsLoading ? (
                <div style={{ color: '#94a3b8', fontSize: '14px', textAlign: 'center', padding: '40px 0' }}>
                  Loading materials...
                </div>
              ) : materials.length === 0 ? (
                <div style={{
                  border: '1px dashed rgba(255,255,255,0.08)',
                  borderRadius: '12px',
                  padding: '40px 20px',
                  textAlign: 'center',
                  color: '#64748b',
                  fontSize: '14px'
                }}>
                  No custom study materials uploaded yet. Paste notes on the left to start grounding your AI tutor.
                </div>
              ) : (
                <div style={styles.materialList}>
                  {materials.map((mat) => (
                    <div key={mat.content_id} style={styles.materialItem}>
                      <div style={styles.materialInfo}>
                        <h4 style={styles.topicName}>{mat.topic}</h4>
                        {mat.pdf_file_name && (
                          <div style={styles.materialMeta}>PDF: {mat.pdf_file_name}</div>
                        )}
                        <span style={styles.chunkBadge}>
                          {mat.pdf_file_name ? 'PDF Notes' : `${mat.chunk_count} Chunks`}
                        </span>
                      </div>
                      <button
                        onClick={() => handleDelete(mat.topic)}
                        style={styles.deleteButton}
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div style={styles.sectionGrid}>
          <div style={styles.sectionCard}>
            <h3 style={styles.sectionTitle}>Account</h3>
            <p style={styles.sectionText}>Update your name, email, and personal preferences. Keep your profile information current for a smoother learning experience.</p>
            <button style={styles.button} onClick={() => window.alert('Account options coming soon')}>
              View account settings
            </button>
          </div>
          <div style={styles.sectionCard}>
            <h3 style={styles.sectionTitle}>Privacy</h3>
            <p style={styles.sectionText}>Control what data is saved and how your learning history is stored. Manage privacy preferences and session retention settings.</p>
            <button style={styles.button} onClick={() => window.alert('Privacy options coming soon')}>
              Manage privacy
            </button>
          </div>
          <div style={styles.sectionCard}>
            <h3 style={styles.sectionTitle}>Notifications</h3>
            <p style={styles.sectionText}>Choose how you want to receive updates, reminders, and learning progress alerts.</p>
            <button style={styles.button} onClick={() => window.alert('Notification settings coming soon')}>
              Notification preferences
            </button>
          </div>
        </div>

        <div style={styles.sectionCard}>
          <h3 style={styles.sectionTitle}>Security</h3>
          <p style={styles.sectionText}>Protect your account with recommended security settings. Sign out of all devices and update your session protection options.</p>
          <button style={styles.dangerButton} onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </div>

      {notification && (
        <div style={{
          ...styles.toast,
          background: notification.type === 'error' ? '#ef4444' : '#10b981'
        }}>
          {notification.text}
        </div>
      )}
    </div>
  )
}

export default Settings
