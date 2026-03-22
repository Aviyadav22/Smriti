import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  compress: true,
  transpilePackages: ["react-pdf"],
  webpack: (config) => {
    // react-pdf requires canvas as optional peer dep — stub it for SSR
    config.resolve.alias.canvas = false;
    return config;
  },
  /* API proxy — rewrites /api/v1/* to the backend during development */
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.BACKEND_URL || "http://127.0.0.1:8000/api/v1"}/:path*`,
      },
    ];
  },

  /* Security headers */
  async headers() {
    // CSP is now handled by middleware (src/middleware.ts) for per-request nonce support.
    // Only non-CSP security headers are set here.
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
