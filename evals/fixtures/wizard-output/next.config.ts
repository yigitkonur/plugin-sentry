import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs/config";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
};

export default withSentryConfig(nextConfig, {
  org: "acme",
  project: "web",
  silent: !process.env.CI,
});
