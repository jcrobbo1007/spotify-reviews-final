import { getRanking, getIssues } from "../../../lib/db";
export async function GET() {
  const [ranking, issues] = await Promise.all([getRanking(), getIssues()]);
  const names = Object.fromEntries(issues.map((i) => [i.issue_id, i]));
  return Response.json(ranking.map((r) => ({ ...r, name: names[r.issue_id]?.name, description: names[r.issue_id]?.description })));
}
