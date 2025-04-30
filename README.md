# ConvertiFile API

## Overview

ConvertiFile is a powerful file conversion API built with FastAPI and can be used concurently with Celery which llows the conversion and/or compression of files between various formats:

- **Images**: Convert between JPG, PNG, WebP, BMP, and more (Using PIL)
- **Audio**: Convert between MP3, WAV, OGG, FLAC, and more (Using FFMpeg)
- **Video**: Convert between MP4, WebM, MKV, and more (Using FFMpeg)
- **Documents**: Convert between PDF, TXT, DOCX, and more (Using LibreOffice CLI)

The API has been built to be paired with my own frontend, [Convertifile App](https://convertifile.toridoesthings.xyz)

## Features

- **Asynchronous Processing**: Large file conversions run in the background
- **Progress Tracking**: Track the status of your conversions
- **Metadata Removal**: Optionally strip metadata from files
- **API**: Easy-to-use REST API
- **Web Interface**: Built-in test interface

## Prerequisites

- Python 3.13+
- Redis server (for Celery task queue)
- FFmpeg (for audio/video conversion)
- Pillow
- Libreoffice CLI

## Docker Support

 The API has been Dockerized, it is recommended that the api be ran within a docker container on a standalone drive/volume

### Build & Run the Docker image:

```bash
docker-compose up --build
```

## Installation

If you prefer running the API directly without Docker, the instructions are below:

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/convertifile-api.git
cd convertifile-api
```

### 2. Set up virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg

#### On Ubuntu/Debian:
```bash
sudo apt update
sudo apt install ffmpeg
```

#### On Windows:
1. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract the downloaded archive
3. Add the `bin` folder to your PATH

#### On macOS:
```bash
brew install ffmpeg
```

## Running the Application

### 1. Start Redis server

Make sure Redis is running on your system.

#### On Linux/macOS:
```bash
sudo service redis-server start
```

#### On Windows:
Recommended to use WLS 

```bash
wls --install
```

Then open Ubuntu's Terminal

```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

Then check whether it returns a response `PONG`

```bash
redis-cli ping
```


### 2. Start Celery worker

```bash
celery -A celery_workers worker --loglevel=info
```

### 3. Start the FastAPI server

```bash
uvicorn main:app --reload --port 9003
```

(Port can be anything you want. Add --proxy-headers if you are using a reverse proxy pointing to the API)

## API Endpoints

### Web Interface
- **GET /** - Access the web test interface (Development Environment Only)

### File Conversion
- **POST /convertifileapp/convert** - Submit a file for conversion
  - Parameters (form data):
    - `file`: The file to convert
    - `convert_to`: Target format (e.g., 'mp3', 'jpg')
    - `format-settings`: Various settings

### Status Checking
- **GET /convertifileapp/status/{task_id}** - Check the status of a conversion task

### Result Retrieval
- **GET /convertifileapp/result/{file_id}** - Download a converted file

### Health Check
- **GET /convertifileapp/health** - Check API health status

## File Support

### Images
- Input formats: JPG, PNG, WebP, BMP, TIFF, HEIF
- Output formats: JPG, PNG, WebP, BMP, TIFF, HEIF

### Audio
- Input formats: MP3, WAV, AAC, FLAC, OGG, OPUS, M4A, WMA
- Output formats: MP3, WAV, FLAC, OGG, AAC, M4A

### Video
- Input formats: MP4, MKV, MOV, AVI, WebM, FLV
- Output formats: MP4, WebM, MKV

### Documents
- Input formats: PDF, DOCX, TXT
- Output formats: PDF, DOCX, TXT

## License

[MIT License](LICENSE)
