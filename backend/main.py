from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import boto3
import json
import os
import uuid

# ── App setup ──────────────────────────────────────────────
app = FastAPI(
    title="Banking Agentic RAG API",
    description="Intelligent financial document analyst for banking",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ───────────────────────────────
class QueryRequest(BaseModel):
    question: str
    user_id:  str = "anonymous"

class QueryResponse(BaseModel):
    answer:     str
    sources:    list
    confidence: float
    query_id:   str
    timestamp:  str

class DocumentUploadResponse(BaseModel):
    message:     str
    document_id: str
    bucket:      str
    timestamp:   str

# ── Health check ────────────────────────────────────────────
@app.get("/health")
def health():
    """ECS uses this endpoint to check the container is alive."""
    return {
        "status":    "healthy",
        "service":   "banking-rag-api",
        "version":   "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# ── Root ────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "message": "Banking Agentic RAG API",
        "version": "1.0.0",
        "docs":    "/docs"
    }

# ── Info ────────────────────────────────────────────────────
@app.get("/info")
def info():
    """Returns runtime environment info."""
    return {
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "project":     os.getenv("PROJECT_NAME", "banking-rag"),
        "region":      os.getenv("AWS_REGION",   "ca-central-1")
    }

# ── Query endpoint ──────────────────────────────────────────
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main agent endpoint.
    Week 3 will replace the placeholder with the full
    LangGraph agent — planner, tools, reflection, synthesis.
    """
    return QueryResponse(
        answer=(
            f"Placeholder response for: '{request.question}'. "
            "Full LangGraph agent wired in Week 3."
        ),
        sources=[
            {
                "document": "placeholder",
                "page":     1,
                "score":    0.95
            }
        ],
        confidence = 0.95,
        query_id   = str(uuid.uuid4()),
        timestamp  = datetime.utcnow().isoformat()
    )

# ── Document list endpoint ──────────────────────────────────
@app.get("/documents")
def list_documents():
    """
    Lists documents ingested into the system.
    Week 2 ingestion pipeline populates this.
    """
    return {
        "documents": [],
        "count":     0,
        "message":   "Ingestion pipeline wired in Week 2"
    }