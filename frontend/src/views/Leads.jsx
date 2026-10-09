import { useState } from 'react'
import { api } from '../api.js'
import { Pill, Status, useLoad, when } from '../ui.jsx'

const STATUSES = ['new', 'contacted', 'booked', 'closed']

export default function Leads({ openConversation }) {
  const [filter, setFilter] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const { data, error, loading, reload } = useLoad(`/admin/leads${filter ? `?status=${filter}` : ''}`)
  const selected = data?.find((l) => l.id === selectedId)
  const [message, setMessage] = useState('')

  const setStatus = async (status) => {
    setMessage('')
    try {
      await api(`/admin/leads/${selected.id}`, { method: 'PATCH', body: { status } })
      reload()
    } catch (e) {
      setMessage(e.message)
    }
  }
  const resend = async () => {
    setMessage('Sending…')
    try {
      await api(`/admin/leads/${selected.id}/notify`, { method: 'POST' })
      setTimeout(() => {
        reload()
        setMessage('')
      }, 1500)
    } catch (e) {
      setMessage(e.message)
    }
  }

  return (
    <>
      <div className="head">
        <h1>Leads</h1>
        <select aria-label="Filter by status" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 'auto' }}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <Status loading={loading} error={error} empty={data && !data.length ? 'No leads yet. They appear when a visitor leaves their details in the chat.' : ''}>
        <div className="split">
          <div className="card table-wrap">
            <table>
              <thead><tr><th>Who</th><th>Priority</th><th>Type</th><th>Status</th></tr></thead>
              <tbody>
                {data?.map((lead) => (
                  <tr key={lead.id} className="row" aria-selected={lead.id === selectedId} onClick={() => setSelectedId(lead.id)}>
                    <td><b>{lead.name}</b><br /><span className="muted small">{when(lead.created_at)}</span></td>
                    <td><Pill kind={lead.priority} /></td>
                    <td>{lead.category}</td>
                    <td>{lead.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card stack">
            {!selected ? <p className="muted">Select a lead to see the details.</p> : (
              <>
                <div>
                  <h2>{selected.name}</h2>
                  <p className="muted small">{selected.contact}{selected.preferred_time ? ` · prefers ${selected.preferred_time}` : ''}</p>
                </div>
                <p style={{ whiteSpace: 'pre-wrap' }}>{selected.reason}</p>
                <p className="small muted">
                  <Pill kind={selected.priority} /> {selected.category} · score {selected.score}/100. Triage is a guide: a person decides.<br />
                  Permission to contact given {when(selected.consent_at)}.
                </p>
                <div>
                  <h3>Team alert</h3>
                  {selected.notification ? (
                    <p className="small">
                      <Pill kind={selected.notification.status} /> after {selected.notification.attempts} {selected.notification.attempts === 1 ? 'attempt' : 'attempts'}
                      {selected.notification.error && <span className="muted"> · {selected.notification.error}</span>}
                    </p>
                  ) : <p className="small muted">None recorded.</p>}
                  {selected.notification?.status !== 'sent' && <button className="btn ghost" onClick={resend}>Resend alert</button>}
                </div>
                <div className="row-actions">
                  {STATUSES.map((s) => (
                    <button key={s} className={s === selected.status ? 'btn' : 'btn ghost'} onClick={() => setStatus(s)} aria-pressed={s === selected.status}>{s}</button>
                  ))}
                </div>
                {selected.conversation_id && <button className="btn ghost" onClick={() => openConversation(selected.conversation_id)}>View the conversation</button>}
                {message && <p className="small muted" role="status">{message}</p>}
              </>
            )}
          </div>
        </div>
      </Status>
    </>
  )
}
