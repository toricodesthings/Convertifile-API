FROM python:3.13.3-alpine3.21

# Install FFmpeg, Rust, Cargo, and other dependencies with Alpine package manager
RUN apk update && apk add --no-cache \
    ffmpeg \
    ffmpeg-libs \
    opus \
    opus-dev \
    build-base \
    gcc \
    musl-dev \
    python3-dev \
    libxml2-dev \
    linux-headers \
    libxslt-dev \
    libffi-dev \
    file \
    curl \
    libreoffice \
    poppler-utils \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && . "$HOME/.cargo/env"

RUN ffmpeg -encoders | grep opus

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
EXPOSE 9003

# Add a delay to ensure Redis is fully started, then start Celery worker and FastAPI
CMD ["sh", "-c", "sleep 1 && celery -A celery_workers worker --loglevel=info --detach -B && uvicorn main:app --proxy-headers --host 0.0.0.0 --port 9003 --workers 3"]