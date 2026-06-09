# SAMI / Southbrook — FreeCAD bridge (Module 2).
#
# Installs FreeCAD headless + the FastAPI surface. The Debian package
# brings in `FreeCAD` Python bindings plus the `freecadcmd` headless
# entrypoint that render_cabinet.py invokes. Image is ~1.5 GB after
# install — acceptable for the dev/CI bridge; a slim production image
# is a later optimisation.
#
# G5 gate: `docker compose exec freecad-bridge freecadcmd --version`
# must report a FreeCAD 1.0+ runtime before render-related tests count
# as passing.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# FreeCAD pulls in a lot of Qt/X11 deps even for headless use — that's
# the cost of the official Debian package. xvfb is included so any
# render that incidentally pokes the Qt event loop has a virtual display.
RUN apt-get update && apt-get install -y --no-install-recommends \
        freecad \
        xvfb \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY scripts/ /app/scripts/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
