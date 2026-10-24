import type { NextConfig } from "next";

// BACKEND_URL is a server-side-only variable (set it on Vercel; it is not exposed to the browser). The rewrite below
// forwards /api/v1/* from the Next.js server to the backend, so the browser only ever makes same-origin requests:
// no CORS configuration, and the backend URL is not in the JavaScript bundle.
const backendUrl =
  process.env.BACKEND_URL ||
  (process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "") : "http://localhost:8000");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
