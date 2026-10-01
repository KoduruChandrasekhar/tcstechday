import type { NextConfig } from "next";

// All data comes from the FastAPI engine; the browser only ever talks to this Next.js server.
const API_URL = process.env.API_URL || "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  // Older links from the walkthrough version of the app keep working.
  async redirects() {
    return [
      ["/stock", "/inventory"], ["/build", "/planner"], ["/blocked", "/promotions/blocked"],
      ["/signoff", "/approvals"], ["/results", "/performance"],
    ].map(([source, destination]) => ({ source, destination, permanent: false }));
  },
};

export default nextConfig;
