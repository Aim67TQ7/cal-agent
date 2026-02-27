import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'

const API = ''  // Same origin in production

function api(token) {
  return axios.create({
    baseURL: API,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}

// ============================================================
// LOGIN
// ============================================================
function LoginPage({ onLogin }) {
  const [mode, setMode] = useState('login') // login | register
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [companyCode, setCompanyCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      if (mode === 'login') {
        const res = await api().post('/auth/login', { email, password })
        onLogin(res.data)
      } else {
        await api().post('/auth/register', {
          email, password, first_name: firstName, last_name: lastName, company_code: companyCode,
        })
        setSuccess('Account created! You can now sign in.')
        setMode('login')
        setFirstName('')
        setLastName('')
        setCompanyCode('')
      }
    } catch (err) {
      setError(err.response?.data?.detail || (mode === 'login' ? 'Login failed' : 'Registration failed'))
    } finally {
      setLoading(false)
    }
  }

  const switchMode = () => {
    setMode(mode === 'login' ? 'register' : 'login')
    setError('')
    setSuccess('')
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 380 }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ fontSize: 36, fontWeight: 800, letterSpacing: -1 }}>cal.gp3.app</div>
          <div style={{ color: 'var(--text-muted)', marginTop: 8, fontSize: 14 }}>Calibration Management Agent</div>
        </div>
        <form onSubmit={handleSubmit} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </div>
          {mode === 'register' && (
            <div style={{ display: 'flex', gap: 10 }}>
              <input type="text" placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)} required style={{ flex: 1 }} />
              <input type="text" placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)} style={{ flex: 1 }} />
            </div>
          )}
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
          <div style={{ position: 'relative' }}>
            <input
              type={showPassword ? 'text' : 'password'}
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{ width: '100%', paddingRight: 44 }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-muted)', fontSize: 18, padding: '4px 6px',
                lineHeight: 1,
              }}
              title={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? '\u25C9' : '\u25CE'}
            </button>
          </div>
          {mode === 'register' && (
            <input type="text" placeholder="Company Code" value={companyCode} onChange={e => setCompanyCode(e.target.value)} required />
          )}
          {error && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>}
          {success && <div style={{ color: 'var(--success)', fontSize: 13 }}>{success}</div>}
          <button type="submit" disabled={loading} style={{ marginTop: 6 }}>
            {loading ? (mode === 'login' ? 'Signing in...' : 'Creating account...') : (mode === 'login' ? 'Sign In' : 'Create Account')}
          </button>
        </form>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <button
            onClick={switchMode}
            style={{
              background: 'none', border: 'none', color: 'var(--accent)',
              cursor: 'pointer', fontSize: 13, textDecoration: 'underline',
            }}
          >
            {mode === 'login' ? "Don't have an account? Register" : 'Already have an account? Sign In'}
          </button>
        </div>
        <div style={{ textAlign: 'center', marginTop: 12, color: 'var(--text-muted)', fontSize: 12 }}>
          Powered by n0v8v
        </div>
      </div>
    </div>
  )
}

// ============================================================
// DASHBOARD
// ============================================================
function Dashboard({ data }) {
  if (!data) return <div style={{ color: 'var(--text-muted)' }}>Loading dashboard...</div>

  const total = data.tool_count || 0
  const current = data.status_summary?.current || 0
  const complianceRate = total > 0 ? Math.round((current / total) * 100) : 0

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>Dashboard</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <StatCard label="Tools" value={data.tool_count || 0} />
        <StatCard label="Compliance" value={`${complianceRate}%`} color={complianceRate >= 90 ? 'var(--success)' : 'var(--warning)'} />
        <StatCard label="Expiring Soon" value={data.status_summary?.expiring_soon || 0} color="var(--warning)" />
        <StatCard label="Overdue" value={data.status_summary?.overdue || 0} color={data.status_summary?.overdue > 0 ? 'var(--danger)' : 'var(--success)'} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <StatCard label="Calibration Records" value={data.calibration_count || 0} />
        <StatCard label="Status Categories" value={Object.keys(data.status_summary || {}).length} />
      </div>

      {data.overdue?.length > 0 && (
        <div className="card" style={{ marginBottom: 20, borderLeft: '3px solid var(--danger)' }}>
          <h3 style={{ marginBottom: 12, fontSize: 15, color: 'var(--danger)' }}>Overdue ({data.overdue.length})</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Tool #</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Type</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Manufacturer</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Due Date</th>
              </tr>
            </thead>
            <tbody>
              {data.overdue.map((item, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 0', fontWeight: 600 }}>{item.number}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{item.type}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{item.manufacturer}</td>
                  <td style={{ padding: '10px 0', color: 'var(--danger)' }}>{item.next_due_date || 'Not set'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.upcoming_expirations?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12, fontSize: 15 }}>Upcoming Expirations (60 days)</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Tool #</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Type</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Manufacturer</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Due Date</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.upcoming_expirations.map((item, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 0', fontWeight: 600 }}>{item.number}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{item.type}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{item.manufacturer}</td>
                  <td style={{ padding: '10px 0' }}>{item.next_due_date}</td>
                  <td style={{ padding: '10px 0' }}>
                    <span className={`badge badge-${item.status === 'expiring_soon' ? 'expiring' : item.status}`}>
                      {(item.status || '').replace(/_/g, ' ')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="card" style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || 'var(--text)' }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

// ============================================================
// UPLOAD
// ============================================================
function UploadPage({ token }) {
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef()

  const handleFile = async (file) => {
    if (!file) return
    setLoading(true)
    setResponse(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await api(token).post('/cal/upload', form)
      setResponse(res.data)
    } catch (err) {
      setResponse({ status: 'error', message: err.response?.data?.detail || 'Upload failed' })
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0])
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>Upload Certificate</h2>
      <div
        className="card"
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        style={{
          textAlign: 'center', padding: 60, cursor: 'pointer',
          borderStyle: 'dashed',
          borderColor: dragOver ? 'var(--accent)' : 'var(--border)',
          background: dragOver ? 'rgba(79,140,255,0.05)' : 'var(--surface)',
        }}
      >
        <div style={{ fontSize: 40, marginBottom: 12 }}>&#128196;</div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>Drop calibration certificate here</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>PDF, JPG, or PNG</div>
        <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={e => handleFile(e.target.files[0])} style={{ display: 'none' }} />
      </div>

      {loading && (
        <div className="card" style={{ marginTop: 16, textAlign: 'center', color: 'var(--accent)' }}>
          Extracting calibration data...
        </div>
      )}

      {response && (
        <div className="card" style={{
          marginTop: 16,
          borderLeft: `3px solid ${response.status === 'success' ? 'var(--success)' : response.status === 'warning' ? 'var(--warning)' : 'var(--danger)'}`,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>{response.status.toUpperCase()}</div>
          <div style={{ fontSize: 14 }}>{response.message}</div>
          {(response.data || response.extracted_data) && (
            <pre style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)', overflow: 'auto' }}>
              {JSON.stringify(response.data || response.extracted_data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

// ============================================================
// QUESTION
// ============================================================
function QuestionPage({ token }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)

  const handleAsk = async (e) => {
    e.preventDefault()
    if (!question.trim()) return
    setLoading(true)
    const q = question
    setQuestion('')
    try {
      const res = await api(token).post('/cal/question', { question: q })
      setHistory(prev => [{ q, a: res.data.answer, ts: new Date() }, ...prev])
    } catch (err) {
      setHistory(prev => [{ q, a: 'Error: ' + (err.response?.data?.detail || 'Request failed'), ts: new Date() }, ...prev])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>Ask the Agent</h2>
      <form onSubmit={handleAsk} style={{ display: 'flex', gap: 10 }}>
        <textarea
          placeholder="Which tools are overdue? What's our compliance rate? List all gaussmeters."
          value={question}
          onChange={e => setQuestion(e.target.value)}
          style={{ flex: 1, minHeight: 80, resize: 'vertical' }}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(e) } }}
        />
        <button type="submit" disabled={loading} style={{ alignSelf: 'flex-end', minWidth: 100 }}>
          {loading ? '...' : 'Ask'}
        </button>
      </form>

      <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {history.map((item, i) => (
          <div key={i} className="card">
            <div style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600, marginBottom: 8 }}>Q: {item.q}</div>
            <div style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{item.a}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>{item.ts.toLocaleTimeString()}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================
// EVIDENCE DOWNLOAD
// ============================================================
function DownloadPage({ token }) {
  const [evidenceType, setEvidenceType] = useState('all_current')
  const [format, setFormat] = useState('json')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    setResult(null)
    try {
      if (format === 'pdf') {
        const res = await api(token).post('/cal/download', { evidence_type: evidenceType, format: 'pdf' }, { responseType: 'blob' })
        const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
        const a = document.createElement('a')
        a.href = url
        a.download = `cal_evidence_${evidenceType}_${new Date().toISOString().slice(0, 10)}.pdf`
        a.click()
        window.URL.revokeObjectURL(url)
        setResult({ status: 'success', package_description: 'PDF downloaded.' })
      } else {
        const res = await api(token).post('/cal/download', { evidence_type: evidenceType, format: 'json' })
        setResult(res.data)
      }
    } catch (err) {
      setResult({ status: 'error', package_description: err.response?.data?.detail || 'Generation failed' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>Audit Evidence</h2>
      <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>Evidence Type</label>
          <select value={evidenceType} onChange={e => setEvidenceType(e.target.value)}>
            <option value="all_current">All Current Calibrations</option>
            <option value="overdue">Overdue Only</option>
            <option value="expiring_soon">Expiring Soon</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>Format</label>
          <select value={format} onChange={e => setFormat(e.target.value)}>
            <option value="json">Summary (Text)</option>
            <option value="pdf">Branded PDF</option>
          </select>
        </div>
        <button onClick={handleGenerate} disabled={loading} style={{ minWidth: 140 }}>
          {loading ? 'Generating...' : format === 'pdf' ? 'Download PDF' : 'Generate Package'}
        </button>
      </div>

      {result && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontWeight: 600 }}>Evidence Package</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {result.record_count != null && `${result.record_count} records`}
              {result.generated_at && ` | ${new Date(result.generated_at).toLocaleString()}`}
            </span>
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {result.package_description}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================
// EQUIPMENT
// ============================================================
function EquipmentPage({ token }) {
  const [equipment, setEquipment] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({
    number: '', type: '', description: '', manufacturer: '', model: '',
    serial_number: '', location: '', building: '', frequency: 'annual', ownership: '',
  })

  useEffect(() => { loadEquipment() }, [])

  const loadEquipment = async () => {
    try {
      const res = await api(token).get('/cal/equipment')
      setEquipment(res.data.equipment)
    } catch { }
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    try {
      await api(token).post('/cal/equipment', form)
      setShowAdd(false)
      setForm({
        number: '', type: '', description: '', manufacturer: '', model: '',
        serial_number: '', location: '', building: '', frequency: 'annual', ownership: '',
      })
      loadEquipment()
    } catch { }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 20 }}>Equipment Registry ({equipment.length})</h2>
        <button onClick={() => setShowAdd(!showAdd)}>{showAdd ? 'Cancel' : '+ Add Tool'}</button>
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="card" style={{ marginBottom: 20, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <input placeholder="Tool Number *" value={form.number} onChange={e => setForm({ ...form, number: e.target.value })} required />
          <input placeholder="Type (e.g., caliper, gauge)" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} />
          <input placeholder="Manufacturer" value={form.manufacturer} onChange={e => setForm({ ...form, manufacturer: e.target.value })} />
          <input placeholder="Model" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} />
          <input placeholder="Serial Number" value={form.serial_number} onChange={e => setForm({ ...form, serial_number: e.target.value })} />
          <input placeholder="Location" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
          <input placeholder="Building" value={form.building} onChange={e => setForm({ ...form, building: e.target.value })} />
          <select value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })}>
            <option value="annual">Annual</option>
            <option value="semi-annual">Semi-Annual</option>
            <option value="quarterly">Quarterly</option>
            <option value="monthly">Monthly</option>
            <option value="as-needed">As Needed</option>
          </select>
          <input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} style={{ gridColumn: '1 / -1' }} />
          <button type="submit" style={{ gridColumn: '1 / -1' }}>Save Tool</button>
        </form>
      )}

      <div className="card" style={{ overflowX: 'auto' }}>
        {equipment.length === 0 && <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 30 }}>No equipment registered yet.</div>}
        {equipment.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Tool #</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Type</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Manufacturer</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Model</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Location</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Frequency</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Last Cal</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Due</th>
                <th style={{ textAlign: 'left', padding: '8px 0' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {equipment.map((eq) => (
                <tr key={eq.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 0', fontWeight: 600 }}>{eq.number}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{eq.type}</td>
                  <td style={{ padding: '10px 0' }}>{eq.manufacturer}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{eq.model}</td>
                  <td style={{ padding: '10px 0', color: 'var(--text-muted)' }}>{eq.location}</td>
                  <td style={{ padding: '10px 0' }}>{eq.frequency}</td>
                  <td style={{ padding: '10px 0' }}>{eq.last_cal_date || '-'}</td>
                  <td style={{ padding: '10px 0' }}>{eq.next_due_date || '-'}</td>
                  <td style={{ padding: '10px 0' }}>
                    {eq.calibration_status && (
                      <span className={`badge badge-${eq.calibration_status === 'expiring_soon' ? 'expiring' : eq.calibration_status}`}>
                        {eq.calibration_status.replace(/_/g, ' ')}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ============================================================
// APP SHELL
// ============================================================
const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: '&#9632;' },
  { id: 'upload', label: 'Upload', icon: '&#8593;' },
  { id: 'question', label: 'Ask Agent', icon: '&#9998;' },
  { id: 'download', label: 'Evidence', icon: '&#8595;' },
  { id: 'equipment', label: 'Equipment', icon: '&#9881;' },
]

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('cal_token'))
  const [company, setCompany] = useState(localStorage.getItem('cal_company'))
  const [page, setPage] = useState('dashboard')
  const [dashData, setDashData] = useState(null)

  useEffect(() => {
    if (token) loadDashboard()
  }, [token])

  const loadDashboard = async () => {
    try {
      const res = await api(token).get('/cal/dashboard')
      setDashData(res.data)
    } catch { }
  }

  const handleLogin = (data) => {
    setToken(data.token)
    setCompany(data.company_name)
    localStorage.setItem('cal_token', data.token)
    localStorage.setItem('cal_company', data.company_name)
  }

  const handleLogout = () => {
    setToken(null)
    setCompany(null)
    localStorage.removeItem('cal_token')
    localStorage.removeItem('cal_company')
  }

  if (!token) return <LoginPage onLogin={handleLogin} />

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div style={{
        width: 220, background: 'var(--surface)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', padding: '20px 0',
      }}>
        <div style={{ padding: '0 20px', marginBottom: 30 }}>
          <div style={{ fontSize: 16, fontWeight: 800 }}>cal.gp3.app</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{company}</div>
        </div>

        <nav style={{ flex: 1 }}>
          {NAV.map(item => (
            <div
              key={item.id}
              onClick={() => { setPage(item.id); if (item.id === 'dashboard') loadDashboard() }}
              style={{
                padding: '10px 20px', cursor: 'pointer', fontSize: 14,
                background: page === item.id ? 'rgba(79,140,255,0.1)' : 'transparent',
                borderLeft: page === item.id ? '3px solid var(--accent)' : '3px solid transparent',
                color: page === item.id ? 'var(--accent)' : 'var(--text)',
              }}
            >
              <span dangerouslySetInnerHTML={{ __html: item.icon }} style={{ marginRight: 10 }} />
              {item.label}
            </div>
          ))}
        </nav>

        <div style={{ padding: '0 20px' }}>
          <button className="btn-secondary" onClick={handleLogout} style={{ width: '100%', fontSize: 13 }}>
            Sign Out
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, padding: 32, maxWidth: 1100 }}>
        {page === 'dashboard' && <Dashboard data={dashData} />}
        {page === 'upload' && <UploadPage token={token} />}
        {page === 'question' && <QuestionPage token={token} />}
        {page === 'download' && <DownloadPage token={token} />}
        {page === 'equipment' && <EquipmentPage token={token} />}
      </div>
    </div>
  )
}
