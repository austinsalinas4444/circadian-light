"""
CircadianLight FastAPI Backend
Main application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import lighting

# Create FastAPI app
app = FastAPI(
    title="CircadianLight API",
    description="Backend API for personalized, biologically-aware circadian lighting recommendations based on health data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for iOS app
# The iOS app connects from localhost (simulator) on port 8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Web development
        "http://localhost:8000",      # iOS simulator
        "http://127.0.0.1:8000",      # iOS simulator alternative
        "*"  # TODO: Restrict to specific origins in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(lighting.router)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint - API health check and info."""
    return {
        "service": "CircadianLight API",
        "status": "healthy",
        "version": "1.0.0",
        "description": "Biologically-aware circadian lighting recommendations"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "ok",
        "service": "circadianlight-api"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload during development
        log_level="info"
    )
