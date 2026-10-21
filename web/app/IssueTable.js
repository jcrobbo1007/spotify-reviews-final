"use client";
import { Fragment, useState } from "react";

export default function IssueTable({ ranking }) {
  const [open, setOpen] = useState(null);
  const [data, setData] = useState({});
  async function toggle(id) {
    if (open === id) return setOpen(null);
    setOpen(id);
    if (!data[id]) {
      const r = await fetch(`/api/issue?id=${encodeURIComponent(id)}`);
      const j = await r.json();
      setData((d) => ({ ...d, [id]: j }));
    }
  }
  return (
    <div className="wrap"><table>
      <thead><tr><th className="n">Rank</th><th>Issue</th><th className="n">Complaints</th><th className="n">Severity sum</th><th className="n">Mean severity</th><th className="n">Priority</th></tr></thead>
      <tbody>{ranking.map((r) => (<Fragment key={r.issue_id}>
        <tr key={r.issue_id}>
          <td className="n">{r.rank}</td>
          <td><button className="link" onClick={() => toggle(r.issue_id)}>{open === r.issue_id ? "▾" : "▸"} <code>{r.issue_id}</code></button><div className="muted">{r.name}</div></td>
          <td className="n">{r.complaint_count}</td><td className="n">{r.severity_sum}</td><td className="n">{r.mean_severity}</td><td className="n">{r.priority_score}</td>
        </tr>
        {open === r.issue_id && (<tr key={r.issue_id + "-d"}><td colSpan={6}><div className="drill">
          {!data[r.issue_id] ? "Loading…" : (<>
            <div className="muted">{r.description} Showing {data[r.issue_id].shown} of {r.complaint_count} member reviews (highest severity first).</div>
            <table><thead><tr><th>Review ID</th><th className="n">Sev</th><th>Intent</th><th>Evidence quote</th></tr></thead>
              <tbody>{data[r.issue_id].members.map((m) => (<tr key={m.review_id}><td><code>{m.review_id}</code></td><td className="n">{m.severity}</td><td>{m.intent}</td><td>{m.evidence_quote}{m.needs_review ? " ⚑" : ""}</td></tr>))}</tbody></table>
          </>)}
        </div></td></tr>)}
      </Fragment>))}</tbody>
    </table></div>
  );
}
