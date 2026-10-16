/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir: process.env.CAR2LEGO_NEXT_DIST || ".next",
  // A specification dialogue can include two model turns of up to five minutes.
  experimental: { proxyTimeout: 660000 },
  eslint: { dirs: ["app", "components", "lib"] },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.CAR2LEGO_API_ORIGIN || "http://127.0.0.1:8767"}/api/:path*` }];
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
};

export default nextConfig;
