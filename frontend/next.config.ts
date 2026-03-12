import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  compress: true,
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
    const isDev = process.env.NODE_ENV === "development";
    const backendUrl = process.env.BACKEND_URL || "";

    // CSP Policy:
    // - script-src: NO 'unsafe-inline' — prevents inline script injection (XSS).
    //   Next.js uses nonce-based inline scripts automatically in production.
    //   'unsafe-eval' is only added in dev mode for hot-reload.
    // - style-src: 'unsafe-inline' is required because Next.js (styled-jsx)
    //   and Tailwind inject <style> tags at runtime. Nonce-based styles are
    //   not yet fully supported by Next.js (see next.js#26891).
    // - connect-src: In production, only 'self' + explicit BACKEND_URL.
    //   In dev, also allow localhost websocket for HMR.
    const connectSrc = isDev
      ? `connect-src 'self' ${backendUrl || "http://127.0.0.1:8000"} ws://localhost:*`
      : `connect-src 'self'${backendUrl ? ` ${backendUrl}` : ""}`;

    const csp = [
      "default-src 'self'",
      `script-src 'self'${isDev ? " 'unsafe-eval'" : ""}`,
      // NOTE: 'unsafe-inline' in style-src is required by Next.js styled-jsx / Tailwind runtime styles.
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://storage.googleapis.com",
      "font-src 'self'",
      connectSrc,
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

export default withNextIntl(nextConfig);
