import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'

export function useLoad(path) {
  const [state, setState] = useState({ data: null, error: '', loading: true })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    api(path)
      .then((data) => !cancelled && setState({ data, error: '', loading: false }))
      .catch((e) => !cancelled && setState({ data: null, error: e.message, loading: false }))
    return () => {
      cancelled = true
    }
  }, [path, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}

export const when = (iso) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''

export const Pill = ({ kind, children }) => <span className={`pill ${kind}`}>{children ?? kind}</span>

export const Status = ({ loading, error, empty, children }) => {
  if (loading) return <p className="muted">Loading…</p>
  if (error) return <p className="err" role="alert">{error}</p>
  if (empty) return <p className="empty">{empty}</p>
  return children
}
