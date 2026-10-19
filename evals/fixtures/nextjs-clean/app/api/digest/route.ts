import { summarize } from "@/lib/openai";

export async function GET() {
  const text = await summarize("Daily digest input");
  return Response.json({ text });
}
