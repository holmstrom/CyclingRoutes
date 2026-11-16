"""
FastAPI application entry point for RouteFinder.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.geocode import router as geocode_router
from backend.api.inspiration import router as inspiration_router
from backend.api.routes import router as routes_router

app = FastAPI(title="RouteFinder API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geocode_router, prefix="/api")
app.include_router(inspiration_router, prefix="/api")
app.include_router(routes_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
