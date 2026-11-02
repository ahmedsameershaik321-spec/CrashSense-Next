import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "crashsense_video_access";
const COOKIE_PATH = "/api/videos";
const MAX_SESSION_SECONDS = 15 * 60;

function isSameOriginRequest(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const forwardedHost = request.headers
    .get("x-forwarded-host")
    ?.split(",")[0]
    ?.trim();
  const host = forwardedHost || request.headers.get("host");
  const forwardedProtocol = request.headers
    .get("x-forwarded-proto")
    ?.split(",")[0]
    ?.trim();
  const protocol = forwardedProtocol || request.nextUrl.protocol.slice(0, -1);
  const expectedOrigin = host ? `${protocol}://${host}` : request.nextUrl.origin;
  return (
    (!origin || origin === expectedOrigin) &&
    request.headers.get("x-crashsense-video-session") === "1"
  );
}

export async function POST(request: NextRequest) {
  if (!isSameOriginRequest(request)) {
    return NextResponse.json(
      { detail: "A same-origin request is required." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return NextResponse.json(
      { detail: "A JSON request body is required." },
      { status: 415, headers: { "Cache-Control": "no-store" } },
    );
  }

  const payload: unknown = await request.json().catch(() => null);
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("accessToken" in payload) ||
    typeof payload.accessToken !== "string" ||
    !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(payload.accessToken) ||
    payload.accessToken.length > 8192 ||
    !("expiresInSeconds" in payload) ||
    typeof payload.expiresInSeconds !== "number" ||
    !Number.isSafeInteger(payload.expiresInSeconds) ||
    payload.expiresInSeconds < 1
  ) {
    return NextResponse.json(
      { detail: "The video access session is invalid." },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const maxAge = Math.min(payload.expiresInSeconds, MAX_SESSION_SECONDS);
  const response = new NextResponse(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
  response.cookies.set(COOKIE_NAME, payload.accessToken, {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: COOKIE_PATH,
    maxAge,
  });
  return response;
}

export function DELETE(request: NextRequest) {
  if (!isSameOriginRequest(request)) {
    return NextResponse.json(
      { detail: "A same-origin request is required." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  const response = new NextResponse(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
  response.cookies.set(COOKIE_NAME, "", {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: COOKIE_PATH,
    maxAge: 0,
  });
  return response;
}
