from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import time
from pathlib import Path
from loguru import logger

from api_routes import convert, status, health, result

# Use Pathlib for paths
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
TEMP_DIR = BASE_DIR / "temp_files"
STATIC_DIR = BASE_DIR / "static"

LOG_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger.configure(
    handlers=[
        {"sink": str(LOG_FILE), "rotation": "10 MB", "retention": "1 day"},
        {"sink": lambda msg: print(msg, end=""), "level": "INFO"}
    ]
)

logger.info(f"Created temporary directory at {TEMP_DIR}")

subapi = FastAPI(
    title="ConvertIFile API",
    description="API for converting files between various formats",
    version="1.0.0",
)

subapi.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://utility.toridoesthings.xyz",
        "https://utility.toridoesthings.xyz",
        "http://convertifile.toridoesthings.xyz",
        "https://convertifile.toridoesthings.xyz"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@subapi.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url.path}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
    return response

@subapi.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_details = traceback.format_exc()
    logger.opt(exception=True).error(f"Unhandled exception: {exc}")
    # Use .casefold() for robust comparison
    if os.getenv("ENVIRONMENT", "development").casefold() == "development":
        return JSONResponse(
            status_code=500,
            content={
                "message": "Internal server error. Please try again later.",
                "error": str(exc),
                "path": request.url.path,
                "method": request.method,
                "details": error_details.split("\n")
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error. Please try again later."}
        )

subapi.include_router(health.router, prefix="/health", tags=["Health"])
subapi.include_router(convert.router, prefix="/convert", tags=["Conversion"])
subapi.include_router(status.router, prefix="/status", tags=["Task Status"])
subapi.include_router(result.router, prefix="/result", tags=["Result"])

app = FastAPI(
    title="ConvertIFile Service",
    description="File conversion service with multiple endpoints",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://utility.toridoesthings.xyz",
        "https://utility.toridoesthings.xyz",
        "http://convertifile.toridoesthings.xyz",
        "https://convertifile.toridoesthings.xyz"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/convertifile/", subapi)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

logger.info("ConvertIFile API initialized successfully")

@app.get("/", tags=["Root"])
def read_root() -> FileResponse:
    logger.info("Root endpoint accessed - serving test interface")
    return FileResponse(str(STATIC_DIR / "index.html"))
