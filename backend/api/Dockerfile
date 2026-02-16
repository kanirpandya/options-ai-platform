# Purpose: Container image for the Options AI Platform v1 FastAPI service (ALB -> ECS Fargate).
# - Builds a slim runtime image with dependencies installed.
# - Runs the API via uvicorn on port 8000.
# Author: Kanir Pandya
# Created: 2026-02-15

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (kept minimal). Add build-essential if you have deps needing compilation.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy repo into image
COPY . /app

# Install Python deps:
# Prefer requirements.txt if present; otherwise install editable if using pyproject.
# If you have a different dependency strategy, adjust this block.
# Install engine package (coveredcall-agents) and its dependencies.
RUN pip install --no-cache-dir -r backend/api/requirements.txt \
 && pip install --no-cache-dir -e engine/coveredcall-agents


EXPOSE 8000

# IMPORTANT: Adjust module path if needed.
# Common candidates:
#   backend.api.main:app
#   api.main:app
#   main:app
CMD ["python", "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
