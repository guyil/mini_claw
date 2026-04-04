const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(request: Request) {
  const body = await request.json();
  const authHeader = request.headers.get("authorization");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (authHeader) {
    headers["Authorization"] = authHeader;
  }

  const backendResp = await fetch(`${BACKEND_URL}/assistant`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  return new Response(backendResp.body, {
    status: backendResp.status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
