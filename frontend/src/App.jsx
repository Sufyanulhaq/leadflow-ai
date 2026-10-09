import { useCallback, useEffect, useState } from 'react'
import { getToken, login, logout, setUnauthorisedHandler } from './api.js'
import Conversations from './views/Conversations.jsx'
import Install from './views/Install.jsx'
import Knowledge from './views/Knowledge.jsx'
import Leads from './views/Leads.jsx'
import Overview from './views/Overview.jsx'
import Unanswered from './views/Unanswered.jsx'

const TABS = [
  ['overview', 'Overview'],
  ['leads', 'Leads'],
  ['conversations', 'Conversations'],
  ['unanswered', 'Questions to add'],
  ['knowledge', 'Knowledge base'],
  ['install', 'Add to website'],
]

function Login({ onDone }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(password)
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="login card stack" onSubmit={submit}>
      <h1>LeadFlow <span style={{ color: 'var(--accent)' }}>admin</span></h1>
      <div>
        <label htmlFor="pw">Password</label>
        <input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus required />
      </div>
      {error && <p className="err" role="alert">{error}</p>}
      <button className="btn" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
  )
}

export default function App() {
  const [signedIn, setSignedIn] = useState(Boolean(getToken()))
  const [tab, setTab] = useState('overview')
  const [conversationId, setConversationId] = useState(null)
  const [draftTitle, setDraftTitle] = useState('')

  useEffect(() => {
    setUnauthorisedHandler(() => {
      logout()
      setSignedIn(false)
    })
  }, [])
  const clearDraft = useCallback(() => setDraftTitle(''), [])

  if (!signedIn) return <Login onDone={() => setSignedIn(true)} />

  return (
    <div className="shell">
      <nav className="side" aria-label="Main">
        <div className="brand">LeadFlow <span>admin</span></div>
        {TABS.map(([id, label]) => (
          <button key={id} className="nav" aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>{label}</button>
        ))}
        <div className="spacer" />
        <button className="nav" onClick={() => { logout(); setSignedIn(false) }}>Sign out</button>
      </nav>
      <main className="main">
        {tab === 'overview' && <Overview go={setTab} />}
        {tab === 'leads' && <Leads openConversation={(id) => { setConversationId(id); setTab('conversations') }} />}
        {tab === 'conversations' && <Conversations selectedId={conversationId} setSelectedId={setConversationId} />}
        {tab === 'unanswered' && <Unanswered addToKnowledge={(q) => { setDraftTitle(q); setTab('knowledge') }} />}
        {tab === 'knowledge' && <Knowledge draftTitle={draftTitle} clearDraft={clearDraft} />}
        {tab === 'install' && <Install />}
      </main>
    </div>
  )
}
