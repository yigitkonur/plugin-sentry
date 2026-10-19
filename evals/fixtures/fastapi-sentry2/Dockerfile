FROM python:3.12-slim
WORKDIR /srv
COPY . .
RUN pip install uv && uv sync --frozen
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
