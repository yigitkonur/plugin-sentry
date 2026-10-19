export async function GET() {
  // nightly digest, triggered by vercel.json cron
  return Response.json({ ran: true });
}
