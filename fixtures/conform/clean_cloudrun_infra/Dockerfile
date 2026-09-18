FROM python:3.12-slim

WORKDIR /app

RUN useradd -u 10001 appuser && chown -R appuser:appuser /app

COPY . /app

USER appuser

EXPOSE 8080

CMD ["python", "-m", "vibe_guard"]
