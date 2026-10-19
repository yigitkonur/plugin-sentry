import Config

config :my_app, MyAppWeb.Endpoint,
  url: [host: "localhost"],
  render_errors: [formats: [json: MyAppWeb.ErrorJSON]]

config :sentry,
  dsn: System.get_env("SENTRY_DSN"),
  environment_name: config_env(),
  enable_source_code_context: true,
  root_source_code_paths: [File.cwd!()]

config :logger, :console, format: "$time $metadata[$level] $message\n"

config :phoenix, :json_library, Jason
