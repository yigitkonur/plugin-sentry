import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import * as Sentry from "@sentry/node";
import { z } from "zod";

const server = new McpServer({ name: "orders-mcp", version: "0.2.0" });

Sentry.init({ dsn: process.env.SENTRY_DSN, sendDefaultPii: true });

server.tool("lookup_order", { orderId: z.string(), customerEmail: z.string() }, async ({ orderId, customerEmail }) => {
  try {
    const res = await fetch(`${process.env.API_URL}/api/orders?id=${orderId}`, { headers: { "x-customer-email": customerEmail } });
    return { content: [{ type: "text", text: await res.text() }] };
  } catch (err) {
    return { content: [{ type: "text", text: "lookup failed" }], isError: true };
  }
});

await server.connect(new StdioServerTransport());
