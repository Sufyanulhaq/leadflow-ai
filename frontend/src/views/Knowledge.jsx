import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Status, useLoad } from '../ui.jsx'

const BLANK = { id: null, title: '', content: '' }

export default function Knowledge({ draftTitle, clearDraft }) {
  const { data, error, loading, reload } = useLoad('/admin/documents')
  const [doc, setDoc] = useState(BLANK)
  const [note, setNote] = useState({ text: '', bad: false })

  useEffect(() => {
    if (draftTitle) {
      setDoc({ ...BLANK, title: draftTitle })
      clearDraft()
    }
  }, [draftTitle, clearDraft])

  const save = async (e) => {
    e.preventDefault()
    setNote({ text: '', bad: false })
    try {
      const saved = doc.id
        ? await api(`/admin/documents/${doc.id}`, { method: 'PUT', body: { title: doc.title, content: doc.content } })
        : await api('/admin/documents', { method: 'POST', body: { title: doc.title, content: doc.content } })
      setDoc({ id: saved.id, title: saved.title, content: saved.content })
      setNote({ text: `Saved. The assistant can use it straight away (${saved.passages} searchable ${saved.passages === 1 ? 'piece' : 'pieces'}).`, bad: false })
      reload()
    } catch (err) {
      setNote({ text: err.message, bad: true })
    }
  }
  const remove = async () => {
    if (!window.confirm(`Delete "${doc.title}"? The assistant will stop using it.`)) return
    try {
      await api(`/admin/documents/${doc.id}`, { method: 'DELETE' })
      setDoc(BLANK)
      setNote({ text: 'Deleted.', bad: false })
      reload()
    } catch (err) {
      setNote({ text: err.message, bad: true })
    }
  }

  return (
    <>
      <div className="head">
        <h1>Knowledge base</h1>
        <button className="btn" onClick={() => { setDoc(BLANK); setNote({ text: '', bad: false }) }}>New document</button>
      </div>
      <p className="muted">The assistant answers only from these documents. Keep each one short and factual: prices, hours, policies. Separate topics with a blank line.</p>
      <Status loading={loading} error={error}>
        <div className="split">
          <div className="card stack">
            {data?.map((d) => (
              <button key={d.id} className={`nav ${d.id === doc.id ? '' : ''}`} aria-current={d.id === doc.id ? 'page' : undefined} onClick={() => { setDoc(d); setNote({ text: '', bad: false }) }}>
                <span>{d.title}</span><span className="small">{d.passages}</span>
              </button>
            ))}
            {data && !data.length && <p className="empty">No documents yet.</p>}
          </div>
          <form className="card stack" onSubmit={save}>
            <div><label htmlFor="t">Title</label><input id="t" type="text" value={doc.title} maxLength={200} required onChange={(e) => setDoc({ ...doc, title: e.target.value })} /></div>
            <div><label htmlFor="c">Content</label><textarea id="c" value={doc.content} maxLength={20000} required onChange={(e) => setDoc({ ...doc, content: e.target.value })} /></div>
            <div className="row-actions">
              <button className="btn" type="submit">{doc.id ? 'Save changes' : 'Add document'}</button>
              {doc.id && <button className="btn danger" type="button" onClick={remove}>Delete</button>}
            </div>
            {note.text && <p className={note.bad ? 'err' : 'ok'} role="status">{note.text}</p>}
          </form>
        </div>
      </Status>
    </>
  )
}
