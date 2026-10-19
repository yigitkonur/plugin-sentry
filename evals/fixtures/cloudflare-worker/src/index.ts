import * as Sentry from "@sentry/cloudflare";
import { Hono } from "hono";

type Bindings = { SENTRY_DSN: string };

const app = new Hono<{ Bindings: Bindings }>();

app.get("/", (c) => c.text("Hello from the edge"));
app.get("/health", (c) => c.json({ ok: true }));

export default Sentry.withSentry(
  (env: Bindings) => ({ dsn: env.SENTRY_DSN, tracesSampleRate: 1.0 }),
  {
    fetch: app.fetch,
    async scheduled(controller: ScheduledController, env: Bindings, ctx: ExecutionContext) {
      console.log("hourly tick", controller.scheduledTime);
    },
  } satisfies ExportedHandler<Bindings>,
);
