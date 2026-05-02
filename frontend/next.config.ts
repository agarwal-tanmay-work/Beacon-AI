import type { NextConfig } from "next";

// BACKEND_URL is a server-side-only env var set on Vercel (not NEXT_PUBLIC_).
// The rewrite proxies /api/v1/* from Vercel's edge to the Render backend,
// which means the browser makes same-origin requests — zero CORS issues.
const backendUrl =
  process.env.BACKEND_URL ||
  (process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "")
    : "http://localhost:8000");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
