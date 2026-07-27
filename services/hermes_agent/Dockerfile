FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hermes_agent ./hermes_agent

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-m", "hermes_agent.main", "check"]

CMD ["python", "-m", "hermes_agent.main", "serve"]
