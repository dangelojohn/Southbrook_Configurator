FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hermes_agent ./hermes_agent

CMD ["python", "-m", "hermes_agent.main", "--name", "HERMES heartbeat", "--summary", "HERMES sidecar is configured. Human approval is still required."]
