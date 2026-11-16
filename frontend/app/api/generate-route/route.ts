/**
 * Proxy for /api/generate-route → FastAPI backend.
 *
 * Using an explicit Next.js Route Handler instead of a next.config rewrite
 * so we can set maxDuration to avoid the 30-second proxy timeout that
 * route generation (30–90s) would otherwise hit.
 */

export const maxDuration = 300; // seconds — no limit in self-hosted Next.js dev

export async function POST(request: Request) {
  const body = await request.json();

  const backendRes = await fetch("http://127.0.0.1:8000/api/generate-route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    // Node.js fetch has no default timeout; the browser UI shows a spinner
    signal: AbortSignal.timeout(300_000),
  });

  const data = await backendRes.json();
  return Response.json(data, { status: backendRes.status });
}
