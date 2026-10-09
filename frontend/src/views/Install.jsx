import { useState } from 'react'

export default function Install() {
  const origin = window.location.origin
  const snippet = `<script src="${origin}/widget.js" defer></script>`
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(snippet)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard can be blocked; the text is selectable */
    }
  }
  return (
    <>
      <div className="head"><h1>Add the chat to a website</h1></div>
      <div className="card stack">
        <p>Paste this line just before <code>&lt;/body&gt;</code> on every page where the chat should appear.</p>
        <pre>{snippet}</pre>
        <div className="row-actions">
          <button className="btn" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
          <a className="btn ghost" href="/demo" target="_blank" rel="noreferrer">Open the demo clinic site</a>
        </div>
        <p className="small muted">
          Different website address from this one? Set <code>LEADFLOW_ALLOWED_ORIGINS</code> on the server to that site (for example <code>https://yourclinic.co.uk</code>) so browsers allow the chat to connect.
          Optional: add <code>data-accent="#0f766e"</code> to the tag to match the clinic's colour.
        </p>
      </div>
    </>
  )
}
