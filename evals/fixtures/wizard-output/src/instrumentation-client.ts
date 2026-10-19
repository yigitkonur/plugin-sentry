import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: "https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567",

  // Forward Sentry logs from the browser.
  enableLogs: true,

  // Capture 100% in dev, 10% in production
  // Adjust based on your traffic volume
  tracesSampleRate: process.env.NODE_ENV === "development" ? 1.0 : 0.1,
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
