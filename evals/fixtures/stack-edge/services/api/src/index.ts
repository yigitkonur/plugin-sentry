import * as Sentry from "@sentry/cloudflare";
import { Hono } from "hono";
import { cors } from "hono/cors";

type Bindings = { SENTRY_DSN: string };

const app = new Hono<{ Bindings: Bindings }>();

app.use(
  "/api/*",
  cors({
    origin: "https://www.example-co.com",
    allowHeaders: ["Content-Type", "Authorization"],
    allowMethods: ["GET", "POST", "OPTIONS"],
  }),
);

app.get("/health", (c) => c.json({ ok: true }));

app.get("/api/orders", (c) => {
  console.log("orders requested", { customer: c.req.header("x-customer-email") });
  return c.json([{ id: 1, total: 42 }]);
});

app.get("/api/boom", () => {
  throw new Error("orders backend unavailable");
});

export default Sentry.withSentry(
  (env: Bindings) => ({
    dsn: env.SENTRY_DSN,
    environment: "production",
    tracesSampleRate: 1.0,
    sendDefaultPii: true,
    integrations: [Sentry.consoleLoggingIntegration({ levels: ["log", "warn", "error"] })],
  }),
  {
    fetch: app.fetch,
    async scheduled(controller: ScheduledController, env: Bindings, ctx: ExecutionContext) {
      console.log("reconcile tick", controller.scheduledTime);
    },
  } satisfies ExportedHandler<Bindings>,
);
