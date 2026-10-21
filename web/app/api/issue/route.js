import { getIssue } from "../../../lib/db";
export async function GET(req) {
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!/^[a-z]+\.[a-z_]+$/.test(id)) return Response.json({ error: "bad issue id" }, { status: 400 });
  return Response.json(await getIssue(id));
}
