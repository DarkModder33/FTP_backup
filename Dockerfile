FROM python:3.12-slim

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure upload directory exists and is owned by appuser
RUN mkdir -p /data/uploads && chown -R appuser:appuser /data/uploads /app

USER appuser

ENV UPLOAD_FOLDER=/data/uploads \
    HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

CMD ["python", "app.py"]
