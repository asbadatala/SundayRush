import type { NextConfig } from "next";

// Same origin: the browser only ever talks to Next.js, which proxies /api/* to FastAPI.
// Session cookies and the Yahoo OAuth callback therefore stay on one origin, and
// provider secrets never leave the backend.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Hide the dev-only "N" indicator; it overlaps the bottom nav. Compile/runtime errors still surface.
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
