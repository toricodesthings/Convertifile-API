FROM python:3.13.3-slim

# Install FFmpeg, Rust, Cargo, and other dependencies with pinned versions
RUN apt-get update && apt-get install -y \
    ffmpeg=7:5.1.6-0+deb12u1 \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libmagic1 \
    libmagic-dev \
    curl \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && . "$HOME/.cargo/env" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p temp_files static

# Set environment variables for Python logging
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Add a delay to ensure Redis is fully started, then start Celery worker and FastAPI
CMD ["sh", "-c", "sleep 1 && celery -A celery_workers worker --loglevel=info --detach -B && uvicorn main:app --host 0.0.0.0 --port 8000"]