import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* API proxy — rewrites /api/v1/* to the backend during development */
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/:path*`,
      },
    ];
  },

  /* Security headers */
  async headers() {
    const isDev = process.env.NODE_ENV === "development";
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const csp = [
      "default-src 'self'",
      `script-src 'self'${isDev ? " 'unsafe-eval'" : ""} 'unsafe-inline'`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://storage.googleapis.com",
      "font-src 'self'",
      `connect-src 'self' ${apiUrl} ${isDev ? "ws://localhost:*" : ""}`,
      "frame-ancestors 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "worker-src 'self' blob:",
    ].join("; ");

    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};

export default nextConfig;
