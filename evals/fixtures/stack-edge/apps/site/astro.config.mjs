import { defineConfig } from "astro/config";
import cloudflare from "@astrojs/cloudflare";
import sentry from "@sentry/astro";

export default defineConfig({
  output: "server",
  site: "https://www.example-co.com",
  adapter: cloudflare(),
  integrations: [sentry()],
});
