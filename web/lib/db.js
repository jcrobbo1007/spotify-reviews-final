// Server-only data access through Supabase's REST API with the public anon key.
// RLS restricts the anon role to SELECT on the dashboard tables. Never imported by client code.
import "server-only";

const URL = process.env.SUPABASE_URL;
const KEY = process.env.SUPABASE_ANON_KEY;

export async function q(path) {
  if (!URL || !KEY) throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY not configured");
  const res = await fetch(`${URL}/rest/v1/${path}`, {
    headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, "Accept-Profile": "public" },
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`db ${res.status}`);
  return res.json();
}

export async function count(table, filter = "") {
  const res = await fetch(`${URL}/rest/v1/${table}?select=review_id${filter ? "&" + filter : ""}`, {
    method: "HEAD",
    headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, Prefer: "count=exact", Range: "0-0" },
    next: { revalidate: 300 },
  });
  const cr = res.headers.get("content-range") || "*/0";
  return Number(cr.split("/")[1]);
}

export const getSummary = async () => Object.fromEntries((await q("run_summary?select=key,value")).map((r) => [r.key, r.value]));
export const getRanking = () => q("ranking?select=*&order=rank.asc");
export const getIssues = () => q("issues?select=*");
export const getMemo = async () => (await q("memo?select=*&id=eq.1"))[0] || null;
export const getClaims = () => q("claims?select=*&order=claim_id.asc");
export async function getIssue(id, limit = 50) {
  const safe = encodeURIComponent(id);
  const members = await q(`membership?select=review_id&issue_id=eq.${safe}&order=review_id.asc&limit=${limit}`);
  const ids = members.map((m) => m.review_id);
  const recs = ids.length
    ? await q(`records?select=review_id,topic,intent,severity,sentiment,evidence_quote,needs_review,review_rating,review_timestamp&review_id=in.(${ids.map(encodeURIComponent).join(",")})`)
    : [];
  return { issue_id: id, shown: recs.length, members: recs.sort((a, b) => b.severity - a.severity || a.review_id.localeCompare(b.review_id)) };
}
