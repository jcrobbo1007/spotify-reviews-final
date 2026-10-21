import { getSummary } from "../../../lib/db";
export async function GET() { return Response.json(await getSummary()); }
