from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import os
import time
import uuid
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from limiter import limiter  
from logging_utils import main_logger, get_request_logger, BASE_DIR, LOG_DIR
from api_routes import convert, status, health, result

# Use Pathlib for paths
LOG_FILE = LOG_DIR / "app.log"
TEMP_DIR = BASE_DIR / "temp_files"
STATIC_DIR = BASE_DIR / "static"

TEMP_DIR.mkdir(exist_ok=True)

# Configure standard Python logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

main_logger.info(f"Created temporary directory at {TEMP_DIR}")

subapi = FastAPI(
    title="ConvertIFile API",
    description="API for converting files between various formats",
    version="1.0.0",
)

# Add these two lines to register the rate limit handler
subapi.state.limiter = limiter
subapi.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    expose_headers=["*"], 
)

subapi.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

@subapi.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:6]  # Shorter ID for logs
    request.state.request_id = request_id
    
    log = get_request_logger(request_id)
    
    start_time = time.time()
    
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host
        
    log.info(f"{request.method} {request.url.path} - Started - IP: {client_ip}")
    response = await call_next(request)
    process_time = time.time() - start_time
    log.info(f"{request.method} {request.url.path} - Completed - Status: {response.status_code} - Time: {process_time:.4f}s")
    return response

@subapi.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_details = traceback.format_exc()
    main_logger.opt(exception=True).error(f"Unhandled exception: {exc}")
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

# Also add rate limit handler to the main app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    expose_headers=["*"], 
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Middleware to block access to static files in production/Docker
class StaticFilesAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if the request is for static files
        if request.url.path.startswith("/static/"):
            # Only allow access in development mode (now checks for Docker)
            if not health.is_development():
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Not Found"}
                )
        
        return await call_next(request)

# Add the middleware
app.add_middleware(StaticFilesAccessMiddleware)

# Mount static files conditionally
if health.is_development():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.mount("/convertifile/", subapi)

main_logger.info("ConvertiFile API initialized successfully")

@app.get("/", tags=["Root"])
def read_root() -> FileResponse:
    if not health.is_development():
        return JSONResponse(
            status_code=200,
            content={"message": "You have accessed Convertifile API's root. Refer to the documentation for usage."},
        )

    main_logger.info("Root endpoint accessed - serving test interface")
    return FileResponse(str(STATIC_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
