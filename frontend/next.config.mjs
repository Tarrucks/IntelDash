/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Kepler.gl + Deck.gl ship ESM and need transpilation when used
  // directly from node_modules. Will switch this on when those packages
  // land in Phase 5 dashboards.
  transpilePackages: [],
};

export default nextConfig;
