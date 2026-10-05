import type { NextConfig } from "next";

// Same origin: the browser only ever talks to Next.js, which proxies /api/* to FastAPI.
// Session cookies and the Yahoo OAuth callback therefore stay on one origin, and
// provider secrets never leave the backend.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
