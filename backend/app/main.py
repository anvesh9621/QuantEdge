from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.db import engine, Base
from app.routes.api import router as api_router

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Stock Market Prediction API",
    description="Backend for Stock Market Prediction and Decision Support System",
    version="1.0.0"
)

# Setup CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Stock Market Prediction API is running"}
