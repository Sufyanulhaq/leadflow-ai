import { useState } from 'react'
import { Status, useLoad, when } from '../ui.jsx'

function Thread({ id }) {
  const { data, error, loading } = useLoad(`/admin/conversations/${id}`)
  return (
    <Status loading={loading} error={error}>
      <div className="chat">
        {data?.messages.map((m) => (
          <div key={m.id} className={`bubble ${m.role} ${m.role === 'assistant' && !m.answerable ? 'miss' : ''}`}>
            {m.text}
            {m.citations?.length > 0 && <div className="src">Based on: {m.citations.map((c) => c.title).join(', ')}</div>}
            {m.role === 'assistant' && <div className="src">{m.mode === 'safety' ? 'Safety reply' : m.answerable ? `Answered (${m.mode})` : 'Could not answer'}</div>}
          </div>
        ))}
      </div>
    </Status>
  )
}

export default function Conversations({ selectedId, setSelectedId }) {
  const { data, error, loading } = useLoad('/admin/conversations')
  const [local, setLocal] = useState(null)
  const active = selectedId || local
  const choose = (id) => {
    setLocal(id)
    setSelectedId?.(null)
  }
  return (
    <>
      <div className="head"><h1>Conversations</h1></div>
      <Status loading={loading} error={error} empty={data && !data.length ? 'No conversations yet. Try the chat on the demo page.' : ''}>
        <div className="split">
          <div className="card table-wrap">
            <table>
              <thead><tr><th>First question</th><th>Msgs</th><th>Missed</th></tr></thead>
              <tbody>
                {data?.map((c) => (
                  <tr key={c.id} className="row" aria-selected={c.id === active} onClick={() => choose(c.id)}>
                    <td>{c.preview}<br /><span className="muted small">{when(c.created_at)}{c.lead_id ? ' · left details' : ''}</span></td>
                    <td>{c.messages}</td>
                    <td>{c.unanswered || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">{active ? <Thread id={active} /> : <p className="muted">Select a conversation to read it.</p>}</div>
        </div>
      </Status>
    </>
  )
}
