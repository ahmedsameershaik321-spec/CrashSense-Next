import type { NextConfig } from "next";

const backendOrigin = (
  process.env.CRASHSENSE_BACKEND_ORIGIN ?? "http://localhost:8000"
).replace(/\/+$/, "");
const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend-api/api/v1";
const localApiBase = publicApiBase.startsWith("/")
  ? publicApiBase.replace(/\/+$/, "")
  : "/backend-api/api/v1";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: `${localApiBase}/:path*`,
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
