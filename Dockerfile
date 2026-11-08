
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY varynx ./varynx

RUN pip install --no-cache-dir .

COPY dashboard_streamlit ./dashboard_streamlit

RUN pip install --no-cache-dir \
    streamlit \
    requests

EXPOSE 8501

CMD ["streamlit", "run", "dashboard_streamlit/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]

