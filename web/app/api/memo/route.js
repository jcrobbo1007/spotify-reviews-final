import { getMemo, getClaims } from "../../../lib/db";
export async function GET() {
  const [memo, claims] = await Promise.all([getMemo(), getClaims()]);
  return Response.json({ memo, claims });
}
