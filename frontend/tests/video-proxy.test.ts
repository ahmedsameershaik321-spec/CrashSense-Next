import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GET as proxyVideoStream } from "@/app/api/videos/[videoId]/stream/route";
import {
  DELETE as clearVideoSession,
  POST as createVideoSession,
} from "@/app/api/video-session/route";

const videoId = "c693e30d-a5a2-4c0d-a4b4-2118102b07f0";
const sameOriginHeaders = {
  origin: "http://localhost:3000",
  "x-crashsense-video-session": "1",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("protected video streaming proxy", () => {
  it("requires a media session and never accepts a token from the URL", async () => {
    const request = new NextRequest(
      `http://localhost:3000/api/videos/${videoId}/stream?token=untrusted`,
    );
    const response = await proxyVideoStream(request, {
      params: Promise.resolve({ videoId }),
    });
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({
      detail: "Authentication is required.",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards the browser Range header and bearer token and preserves partial headers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("partial-video-data", {
          status: 206,
          headers: {
            "Accept-Ranges": "bytes",
            "Content-Length": "18",
            "Content-Range": "bytes 0-17/100",
            "Content-Type": "video/mp4",
          },
        }),
      ),
    );
    const request = new NextRequest(
      `http://localhost:3000/api/videos/${videoId}/stream`,
      {
        headers: {
          cookie: "crashsense_video_access=operator-jwt-token",
          range: "bytes=0-17",
        },
      },
    );
    const response = await proxyVideoStream(request, {
      params: Promise.resolve({ videoId }),
    });

    expect(response.status).toBe(206);
    expect(response.headers.get("accept-ranges")).toBe("bytes");
    expect(response.headers.get("content-range")).toBe("bytes 0-17/100");
    expect(response.headers.get("content-length")).toBe("18");
    expect(await response.text()).toBe("partial-video-data");
    expect(fetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/videos/${videoId}/stream`,
      expect.objectContaining({
        headers: expect.any(Headers),
        cache: "no-store",
        redirect: "manual",
      }),
    );
    const forwardedHeaders = vi.mocked(fetch).mock.calls[0][1]?.headers as Headers;
    expect(forwardedHeaders.get("authorization")).toBe(
      "Bearer operator-jwt-token",
    );
    expect(forwardedHeaders.get("range")).toBe("bytes=0-17");
  });

  it("rejects invalid video identifiers before contacting the backend", async () => {
    const request = new NextRequest(
      "http://localhost:3000/api/videos/../../auth/stream",
    );
    const response = await proxyVideoStream(request, {
      params: Promise.resolve({ videoId: "../../auth" }),
    });
    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("short-lived video media session", () => {
  it("sets an HttpOnly, SameSite cookie scoped to protected video routes", async () => {
    const request = new NextRequest("http://localhost:3000/api/video-session", {
      method: "POST",
      headers: {
        ...sameOriginHeaders,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        accessToken: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature",
        expiresInSeconds: 1800,
      }),
    });
    const response = await createVideoSession(request);
    expect(response.status).toBe(204);
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=strict");
    expect(cookie).toContain("Path=/api/videos");
    expect(cookie).toContain("Max-Age=900");
  });

  it("rejects cross-origin and invalid session requests and clears on logout", async () => {
    const crossOriginRequest = new NextRequest(
      "http://localhost:3000/api/video-session",
      {
        method: "POST",
        headers: {
          origin: "https://attacker.example",
          "x-crashsense-video-session": "1",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          accessToken: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature",
          expiresInSeconds: 100,
        }),
      },
    );
    expect((await createVideoSession(crossOriginRequest)).status).toBe(403);

    const invalidRequest = new NextRequest(
      "http://localhost:3000/api/video-session",
      {
        method: "POST",
        headers: {
          ...sameOriginHeaders,
          "content-type": "application/json",
        },
        body: JSON.stringify({ accessToken: "", expiresInSeconds: 900 }),
      },
    );
    expect((await createVideoSession(invalidRequest)).status).toBe(400);

    const deleteRequest = new NextRequest(
      "http://localhost:3000/api/video-session",
      { method: "DELETE", headers: sameOriginHeaders },
    );
    const deleteResponse = clearVideoSession(deleteRequest);
    expect(deleteResponse.status).toBe(204);
    expect(deleteResponse.headers.get("set-cookie")).toContain("Max-Age=0");
  });
});
