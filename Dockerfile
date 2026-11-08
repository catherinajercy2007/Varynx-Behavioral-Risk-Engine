
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Copy Python project metadata
COPY pyproject.toml README.md ./

# Copy backend application
COPY varynx ./varynx

# Install application dependencies
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn varynx.api.app:app --host 0.0.0.0 --port ${PORT}"]
