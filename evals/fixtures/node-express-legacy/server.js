const express = require("express");
const Raven = require("raven");
const Sentry = require("@sentry/node");
const Tracing = require("@sentry/tracing");

const app = express();

Raven.config(process.env.SENTRY_DSN).install();

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  integrations: [new Tracing.Integrations.Express({ app })],
  tracesSampleRate: 1.0,
});

app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());
app.use("/health", require("./routes/health"));
app.use(Sentry.Handlers.errorHandler());

app.listen(3000, () => console.log("listening on 3000"));
