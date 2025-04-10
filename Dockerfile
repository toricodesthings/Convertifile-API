FROM python:3.13-slim


# Install FFmpeg and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -U "celery[redis]" && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .


# Create necessary directories
RUN mkdir -p temp_files static

# Create logs directory
RUN mkdir -p /app/logs
VOLUME /app/logs

# Set environment variables for Python logging
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Add a delay to ensure Redis is fully started, then start Celery worker and FastAPI
CMD ["sh", "-c", "sleep 2 && celery -A celery_workers worker --loglevel=info --detach && uvicorn main:app --host 0.0.0.0 --port 8000"]