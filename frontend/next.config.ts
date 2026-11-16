import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // generate-route is handled by app/api/generate-route/route.ts
      // (needs maxDuration > 30s — rewrite proxy has a hard 30s limit)
      {
        source: "/api/health",
        destination: "http://127.0.0.1:8000/api/health",
      },
      {
        source: "/api/geocode",
        destination: "http://127.0.0.1:8000/api/geocode",
      },
      {
        source: "/api/route/:path*",
        destination: "http://127.0.0.1:8000/api/route/:path*",
      },
      {
        source: "/api/inspiration/:path*",
        destination: "http://127.0.0.1:8000/api/inspiration/:path*",
      },
    ];
  },
};

export default nextConfig;
