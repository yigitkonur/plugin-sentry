defmodule MyApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :my_app,
      version: "0.1.0",
      elixir: "~> 1.16",
      start_permanent: Mix.env() == :prod,
      deps: deps()
    ]
  end

  def application do
    [mod: {MyApp.Application, []}, extra_applications: [:logger, :runtime_tools]]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7.14"},
      {:sentry, "~> 10.8"},
      {:hackney, "~> 1.20"},
      {:jason, "~> 1.4"}
    ]
  end
end
