/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },

  // Production builds must not share a directory with the dev server.
  // `next build` and `next dev` emit different chunk layouts into the same
  // .next directory, so a build run while dev is live leaves the dev server
  // serving HTML that references chunks which no longer exist — the page then
  // 500s and the stylesheet 404s, showing the user unstyled HTML.
  // build-prod.mjs points this at .next-build.
  distDir: process.env.NEXT_DIST_DIR || ".next",

  // The frontend talks to the backend through a same-origin proxy. Without
  // this, every /api call from the browser hits the Next dev server itself and
  // 404s, so the UI silently renders empty state (0 units, DB offline) even
  // while the backend is healthy. Override with API_ORIGIN for other hosts.
  async rewrites() {
    const origin = process.env.API_ORIGIN || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${origin}/api/:path*` }];
  },
};
export default nextConfig;
