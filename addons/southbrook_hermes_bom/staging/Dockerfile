# SPDX-License-Identifier: LGPL-3.0-only
#
# Tiny image for the staging Hermes mock. Python stdlib only — no deps
# to pin, no wheels to fetch. Total layer count: 2.
#
# Build:
#   docker build -t southbrook/hermes-bom-mock:dev -f staging/Dockerfile staging/
#
# Run (loopback inside container only — publish via -p on the host):
#   docker run --rm -p 7100:7100 \
#     -e HERMES_MOCK_TOKEN=TEST-KEY \
#     southbrook/hermes-bom-mock:dev
#
# Or via the sibling docker-compose.yml (preferred for staging stacks).
FROM python:3.12-slim AS runtime

# Non-root for safety. /home/mock is read-only at runtime.
RUN useradd --create-home --shell /usr/sbin/nologin mock
WORKDIR /home/mock
COPY --chown=mock:mock mock_hermes_server.py /home/mock/mock_hermes_server.py
USER mock

# Sensible defaults; override via -e at runtime.
ENV HERMES_MOCK_HOST=0.0.0.0 \
    HERMES_MOCK_PORT=7100 \
    HERMES_MOCK_TOKEN=TEST-KEY

EXPOSE 7100

# Liveness probe (BaseHTTPServer has no /readyz — /health is enough).
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD python3 -c "import urllib.request, os; \
                    urllib.request.urlopen('http://127.0.0.1:' \
                        + os.environ.get('HERMES_MOCK_PORT','7100') \
                        + '/health', timeout=2).read()" || exit 1

CMD ["sh", "-c", \
     "exec python3 mock_hermes_server.py \
        --host \"$HERMES_MOCK_HOST\" \
        --port \"$HERMES_MOCK_PORT\" \
        --token \"$HERMES_MOCK_TOKEN\""]
