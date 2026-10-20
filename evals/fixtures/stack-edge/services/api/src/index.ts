import * as Sentry from "@sentry/cloudflare";
import { Hono } from "hono";
import { cors } from "hono/cors";
import { WorkerEntrypoint } from "cloudflare:workers";

type Bindings = { SENTRY_DSN: string };

// Called by the site Worker through a service binding (RPC).
export class OrdersRpc extends WorkerEntrypoint<Bindings> {
  async listOrders() {
    return [{ id: 1, total: 42 }];
  }
}

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
