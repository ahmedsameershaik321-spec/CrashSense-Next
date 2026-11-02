import { NextRequest, NextResponse } from "next/server";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function backendStreamUrl(videoId: string): string {
  const backendOrigin = (
    process.env.CRASHSENSE_BACKEND_ORIGIN ?? "http://localhost:8000"
  ).replace(/\/+$/, "");
  return `${backendOrigin}/api/v1/videos/${videoId}/stream`;
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ videoId: string }> },
) {
  const { videoId } = await context.params;
  if (!UUID_PATTERN.test(videoId)) {
    return NextResponse.json(
      { detail: "Video not found." },
      { status: 404, headers: { "Cache-Control": "no-store" } },
    );
  }

  const token = request.cookies.get("crashsense_video_access")?.value;
  if (!token) {
    return NextResponse.json(
      { detail: "Authentication is required." },
      {
        status: 401,
        headers: {
          "Cache-Control": "private, no-store",
          "WWW-Authenticate": "Bearer",
        },
      },
    );
  }

  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const range = request.headers.get("range");
  if (range) {
    headers.set("Range", range);
  }

  let upstream: Response;
  try {
    upstream = await fetch(backendStreamUrl(videoId), {
      method: "GET",
      headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return NextResponse.json(
      { detail: "Video streaming is temporarily unavailable." },
      { status: 502, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  const responseHeaders = new Headers({
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  });
  for (const headerName of [
    "accept-ranges",
    "content-length",
    "content-range",
    "content-type",
    "www-authenticate",
  ]) {
    const value = upstream.headers.get(headerName);
    if (value) {
      responseHeaders.set(headerName, value);
    }
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
