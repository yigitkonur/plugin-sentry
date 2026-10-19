var builder = WebApplication.CreateBuilder(args);

builder.WebHost.UseSentry(o =>
{
    o.Dsn = "https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567";
    o.TracesSampleRate = 1.0;
    o.SendDefaultPii = true;
});

builder.Services.AddControllers();

var app = builder.Build();
app.MapControllers();
app.Run();
