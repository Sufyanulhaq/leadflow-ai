import { Status, useLoad, when } from '../ui.jsx'

export default function Unanswered({ addToKnowledge }) {
  const { data, error, loading } = useLoad('/admin/unanswered')
  return (
    <>
      <div className="head"><h1>Questions to add</h1></div>
      <p className="muted">Visitors asked these and the assistant could not find an answer in your information. Adding the answer means the next visitor gets it.</p>
      <Status loading={loading} error={error} empty={data && !data.length ? 'Nothing missed so far.' : ''}>
        <div className="card table-wrap">
          <table>
            <thead><tr><th>Question</th><th>Asked</th><th /></tr></thead>
            <tbody>
              {data?.map((q, i) => (
                <tr key={i}>
                  <td>{q.question}</td>
                  <td className="muted small">{when(q.asked_at)}</td>
                  <td><button className="btn ghost" onClick={() => addToKnowledge(q.question)}>Write the answer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Status>
    </>
  )
}
