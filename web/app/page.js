import { getSummary, getRanking, getIssues, getMemo, getClaims } from "../lib/db";
import IssueTable from "./IssueTable";

export const revalidate = 300;

function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
// Minimal, escape-first Markdown: headings, bullet lists, paragraphs, **bold**, `code`.
function md(src) {
  const out = [];
  let list = false;
  for (const line of esc(src).split("\n")) {
    const l = line.trim();
    if (/^- /.test(l)) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${l.slice(2)}</li>`); continue; }
    if (list) { out.push("</ul>"); list = false; }
    if (/^#{1,3} /.test(l)) out.push(`<h3>${l.replace(/^#+ /, "")}</h3>`);
    else if (l) out.push(`<p>${l}</p>`);
  }
  if (list) out.push("</ul>");
  return out.join("").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
}
const fmt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : n ?? "—");

export default async function Page() {
  const [s, ranking, issues, memo, claims] = await Promise.all([getSummary(), getRanking(), getIssues(), getMemo(), getClaims()]);
  const names = Object.fromEntries(issues.map((i) => [i.issue_id, i]));
  const rows = ranking.map((r) => ({ ...r, name: names[r.issue_id]?.name, description: names[r.issue_id]?.description }));
  const c = s.counts || {};
  const tiles = [
    ["Source rows accounted", fmt(c.source_rows)], ["Declared subset", fmt(c.subset_rows)], ["Completed", fmt(c.completed)],
    ["Quarantined (subset)", fmt(c.quarantined_subset)], ["Empty-text quarantines", fmt(c.empty_text_quarantines)],
    ["Not in model scope", fmt(c.not_in_model_scope)], ["Cache reuse (rows)", fmt(c.cache_reused_rows)],
    ["Issues ranked", fmt(ranking.length)], ["API spend (USD)", s.cost?.api_spend_usd ?? "—"], ["Spend cap (USD)", s.cost?.cap_usd ?? "—"],
  ];
  return (<main>
    <h1>Spotify review priorities</h1>
    <div className="muted">Saved stage outputs only — no live model calls. Numbers come from ranking.csv and the saved run summary.</div>
    <div className="scope"><strong>{s.scope_label || "Declared subset"}</strong> — {s.scope_detail || ""}</div>
    <div className="grid">{tiles.map(([k, v]) => (<div className="tile" key={k}><div className="v">{v}</div><div className="k">{k}</div></div>))}</div>
    <h2>Stored AI recommendation</h2>
    {memo ? (<div className="memo"><p className="muted">Recommendation: <strong>{memo.recommendation}</strong> (stage-6 output, code-checked)</p>
      <div dangerouslySetInnerHTML={{ __html: md(memo.memo_markdown) }} />
      <h3>Cited numbers (claims.csv)</h3>
      <div className="wrap"><table><thead><tr><th>Claim</th><th>Issue</th><th>Metric</th><th className="n">Value</th></tr></thead>
        <tbody>{claims.map((x) => (<tr key={x.claim_id}><td>{x.claim_id}</td><td><code>{x.issue_id}</code></td><td>{x.metric}</td><td className="n">{x.value}</td></tr>))}</tbody></table></div>
      <p className="muted">Cited review IDs: {(memo.cited_review_ids || []).join(", ")}</p></div>) : <p>No memo loaded.</p>}
    <h2>Issue ranking (baseline: priority = complaint_count × mean_severity)</h2>
    <p className="muted">Click an issue to see member review IDs and evidence quotes. ⚑ = needs_review.</p>
    <IssueTable ranking={rows} />
  </main>);
}
