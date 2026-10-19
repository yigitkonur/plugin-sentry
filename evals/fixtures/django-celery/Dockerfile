FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .
EXPOSE 8000
CMD ["uv", "run", "gunicorn", "config.wsgi", "-b", "0.0.0.0:8000"]
