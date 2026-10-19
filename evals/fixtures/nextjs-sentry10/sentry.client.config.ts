import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: "https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567",
  sendDefaultPii: true,
  tracesSampleRate: 1,
  enableTracing: true,
  replaysSessionSampleRate: 1.0,
  replaysOnErrorSampleRate: 1.0,
  integrations: [Sentry.replayIntegration({ maskAllText: false, blockAllMedia: false })],
});
