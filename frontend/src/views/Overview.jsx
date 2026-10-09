import { Status, useLoad } from '../ui.jsx'

export default function Overview({ go }) {
  const { data, error, loading } = useLoad('/admin/stats')
  return (
    <>
      <div className="head"><h1>Overview</h1></div>
      <Status loading={loading} error={error}>
        {data && (
          <>
            <div className="grid">
              <div className="card stat"><span className="muted small">Conversations</span><b>{data.conversations}</b></div>
              <div className="card stat">
                <span className="muted small">Questions answered</span>
                <b>{data.answered_rate === null ? 'n/a' : `${Math.round(data.answered_rate * 100)}%`}</b>
                <span className="muted small">of {data.assistant_replies} replies</span>
              </div>
              <div className="card stat"><span className="muted small">Leads</span><b>{data.leads}</b></div>
              <div className="card stat"><span className="muted small">High priority</span><b>{data.leads_by_priority.high}</b></div>
            </div>
            <div className="split">
              <div className="card stack">
                <h2>Needs attention</h2>
                {data.leads_by_status.new > 0 && (
                  <p><b>{data.leads_by_status.new}</b> new {data.leads_by_status.new === 1 ? 'lead is' : 'leads are'} waiting. <button className="btn ghost" onClick={() => go('leads')}>Open leads</button></p>
                )}
                {data.notifications_failed > 0 && (
                  <p className="err"><b>{data.notifications_failed}</b> team {data.notifications_failed === 1 ? 'alert' : 'alerts'} failed to send. Open the lead and press Resend.</p>
                )}
                {data.assistant_replies - Math.round((data.answered_rate ?? 1) * data.assistant_replies) > 0 && (
                  <p>Some questions could not be answered. <button className="btn ghost" onClick={() => go('unanswered')}>See what to add</button></p>
                )}
                {!data.leads_by_status.new && !data.notifications_failed && <p className="muted">Nothing needs attention.</p>}
              </div>
              <div className="card stack">
                <h2>Setup</h2>
                <p className={data.ai_configured ? 'ok' : 'muted'}>{data.ai_configured ? 'Claude is connected.' : 'Claude is not connected: answers use the built-in offline answerer. Set ANTHROPIC_API_KEY to enable it.'}</p>
                <p className={data.notifications_configured ? 'ok' : 'muted'}>{data.notifications_configured ? 'Team alerts are configured.' : 'Team alerts are off. Set LEADFLOW_NOTIFY_WEBHOOK_URL to a Slack webhook.'}</p>
              </div>
            </div>
          </>
        )}
      </Status>
    </>
  )
}
