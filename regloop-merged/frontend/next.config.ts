/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for Codespaces: allow the dev server to accept requests
  // from the forwarded *.app.github.dev hostname
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [{ key: "Access-Control-Allow-Origin", value: "*" }],
      },
    ];
  },
};

export default nextConfig;
