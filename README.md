# ConvertiFile API

ConvertiFile is a powerful file conversion API built with FastAPI and Celery that allows you to convert files between various formats:

- **Images**: Convert between JPG, PNG, WebP, BMP, and more
- **Audio**: Convert between MP3, WAV, OGG, FLAC, and more
- **Video**: Convert between MP4, WebM, MKV, and more
- **Documents**: Convert between PDF, TXT, DOCX, and more

## Features

- **Asynchronous Processing**: Large file conversions run in the background
- **Progress Tracking**: Track the status of your conversions
- **Metadata Removal**: Optionally strip metadata from files
- **API**: Easy-to-use REST API
- **Web Interface**: Built-in test interface

## Prerequisites

- Python 3.12+
- Redis server (for Celery task queue)
- FFmpeg (for audio/video conversion)
- Libreoffice CLI

## Installation

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
uvicorn main:app --reload --port 8000
```

## API Endpoints

### Web Interface
- **GET /** - Access the web test interface

### File Conversion
- **POST /convertifileapp/convert** - Submit a file for conversion
  - Parameters (form data):
    - `file`: The file to convert
    - `convert_to`: Target format (e.g., 'mp3', 'jpg')
    - `remove_metadata`: Whether to strip metadata (boolean)

### Status Checking
- **GET /convertifileapp/status/{task_id}** - Check the status of a conversion task

### Result Retrieval
- **GET /convertifileapp/result/{file_id}** - Download a converted file

### Health Check
- **GET /convertifileapp/health** - Check API health status

## API Documentation

After starting the server, you can access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## File Support

### Images
- Input formats: JPG, PNG, WebP, GIF, BMP, TIFF
- Output formats: JPG, PNG, WebP, GIF, BMP, TIFF

### Audio
- Input formats: MP3, WAV, AAC, FLAC, OGG, OPUS, M4A, WMA
- Output formats: MP3, WAV, FLAC, OGG, AAC, M4A

### Video
- Input formats: MP4, MKV, MOV, AVI, WebM, FLV
- Output formats: MP4, WebM, MKV

### Documents
- Input formats: PDF, DOCX, TXT
- Output formats: PDF, DOCX, TXT

## Docker Support

 The API has been Dockerized, it is recommended that the api be ran within a docker container on a standalone drive/volume

### Build & Run the Docker image:

```bash
docker-compose up --build
```

## License

[MIT License](LICENSE)
