FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 GRADIO_ANALYTICS_ENABLED=False
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
COPY coach ./coach
RUN useradd -m appuser && mkdir -p /tmp/coach_data && chown -R appuser /app /tmp/coach_data
USER appuser
# Cloud Run sets PORT (8080). Keys arrive as environment variables from Secret Manager.
CMD ["python", "app.py"]
