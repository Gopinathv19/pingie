import type { NextConfig } from "next";

// Where ping-backend runs. Server-side only (no NEXT_PUBLIC_): the browser
// never calls the backend directly. Every /api/v1/* request goes to this app
// and is forwarded, so the session cookie is first-party in development and
// in production alike, and there is no CORS to configure for the dashboard.
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8080").replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // localhost and 127.0.0.1 are different origins; Next 16 rejects dev
  // requests (including HMR) from origins it does not know.
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  experimental: {
    // The rewrite proxy aborts with a bare 500 after 30s by default. A test or
    // chat request can wait on Memora (180s) and then VizhiOps (180s), so stay
    // above both and let the backend finish or return its own error.
    proxyTimeout: 420_000,
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${BACKEND_URL}/api/v1/:path*` }];
  },
};

export default nextConfig;
