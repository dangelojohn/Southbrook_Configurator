# SAMI / Southbrook — FreeCAD bridge skeleton (Module 0).
#
# This is a placeholder image: it only serves GET /health. Module 2 will
# replace this base with one that installs FreeCAD 1.0 AppImage and the
# freecadcmd entrypoint (G5 gate). Keep this slim until then.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
