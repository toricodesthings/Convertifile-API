FROM python:3.11-slim

# Install FFmpeg and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p temp_files static

# Expose port
EXPOSE 8000

# Start Celery worker and FastAPI server
CMD ["sh", "-c", "celery -A celery_workers worker --loglevel=info --detach && uvicorn main:app --host 0.0.0.0 --port 8000"]
