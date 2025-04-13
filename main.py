from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from api_routes import convert, status, health, result
import os
import logging
import time
from loguru import logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger.configure(
    handlers=[
        {"sink": "app.log", "rotation": "10 MB", "retention": "1 day"},
        {"sink": lambda msg: print(msg, end=""), "level": "INFO"}
    ]
)

# Define TEMP_DIR at the app level for consistency
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)
logger.info(f"Created temporary directory at {TEMP_DIR}")

subapi = FastAPI(
    title="ConvertIFile API",
    description="API for converting files between various formats",
    version="1.0.0",
)

# Add CORS middleware to subapi
subapi.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your React frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# Middleware for request logging
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
    logger.error(f"Unhandled exception: {str(exc)}\n{error_details}")
    
    # Return a more informative error message in development
    if os.getenv("ENVIRONMENT", "development").lower() == "development":
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
        # In production, hide error details
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error. Please try again later."}
        )


# API routes
subapi.include_router(health.router, prefix="/health", tags=["Health"])
subapi.include_router(convert.router, prefix="/convert", tags=["Conversion"])
subapi.include_router(status.router, prefix="/status", tags=["Task Status"])
subapi.include_router(result.router, prefix="/result", tags=["Result"])


# Mount the API @ /convertifileapp
app = FastAPI(
    title="ConvertIFile Service",
    description="File conversion service with multiple endpoints",
    version="1.0.0",
)

# Add CORS middleware to main app as well
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/convertifileapp/", subapi)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

logger.info("ConvertIFile API initialized successfully")

@app.get("/", tags=["Root"])
def read_root():
    logger.info("Root endpoint accessed - serving test interface")
    return FileResponse("static/index.html")
