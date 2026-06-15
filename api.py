"""
FastAPI service that exposes the InvincibleRAG engine to external clients.

Key routes:
- GET /api/health: basic health check
- GET /api/stats: collection statistics
- GET /api/files: list uploaded files
- POST /api/upload: ingest one or more files
- POST /api/chat: generate an answer for a query
- DELETE /api/files/{filename}: remove a file from the vector store
- POST /api/feedback: save a correction for future retrieval

How to run:
- Ensure `.env` is configured
- Start with:
  `.venv312/bin/uvicorn api:app --host 0.0.0.0 --port 8000`
- Connect the React frontend to `http://localhost:8000`
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional
from urllib.parse import unquote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag import InvincibleRAG
from video_gen import VideoGenerator


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    bad_answer: str = Field(min_length=1)
    correction: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class VideoRequest(BaseModel):
    session_id: str = Field(min_length=1)
    query: Optional[str] = None  # optional — generates fresh answer if not provided


@lru_cache(maxsize=1)
def get_rag() -> InvincibleRAG:
    return InvincibleRAG()


def get_video_generator() -> VideoGenerator:
    return VideoGenerator(output_dir="./videos")


# ... (imports)
from fastapi.staticfiles import StaticFiles

# ... (models and helper functions)

app = FastAPI(title="INVINCIBLE API", version="1.0.0")

# Mount static files to serve generated videos
if not os.path.exists("./videos"):
    os.makedirs("./videos")
app.mount("/videos", StaticFiles(directory="./videos"), name="videos")

app.add_middleware(
# ... (rest of middleware)
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    rag = get_rag()
    return {
        "status": "ok",
        "embedding_model": rag.embedding_model_name,
        "generation_candidates": rag.generation_model_candidates,
    }


@app.get("/api/stats")
def stats() -> dict:
    return get_rag().get_stats()


@app.get("/api/files")
def list_files() -> dict:
    return {"files": get_rag().list_ingested_files()}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)) -> dict:
    rag = get_rag()
    results = []
    for upload in files:
        try:
            content = await upload.read()
            chunks = rag.ingest_file(upload.filename, content)
            results.append(
                {
                    "filename": upload.filename,
                    "chunks": chunks,
                    "status": "success",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "filename": upload.filename,
                    "chunks": 0,
                    "status": "error",
                    "error": str(exc),
                }
            )
    return {"results": results}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    rag = get_rag()
    if not rag.list_ingested_files():
        raise HTTPException(status_code=400, detail="Please upload at least one document first.")
    try:
        answer = rag.generate_answer(request.query, request.session_id)
        # Ensure all fields are JSON-serializable
        return {
            "answer": str(answer.get("answer", "")),
            "sources": answer.get("sources", []),
            "chunks_used": answer.get("chunks_used", []),
            "model": str(answer.get("model", "")),
            "scores": answer.get("scores", []),
        }
    except Exception as exc:
        error_msg = str(exc).replace("\n", " ").replace('"', "'")
        raise HTTPException(status_code=500, detail=error_msg) from exc


@app.delete("/api/files/{filename:path}")
def delete_file(filename: str) -> dict:
    decoded = unquote(filename)
    rag = get_rag()
    existing = set(rag.list_ingested_files())
    if decoded not in existing:
        raise HTTPException(status_code=404, detail="File not found.")
    rag.delete_file(decoded)
    return {"deleted": decoded}


@app.post("/api/feedback")
def feedback(request: FeedbackRequest) -> dict:
    rag = get_rag()
    try:
        rag.record_feedback(
            query=request.query,
            bad_answer=request.bad_answer,
            correction=request.correction,
            session_id=request.session_id,
        )
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate-video")
def generate_video(request: VideoRequest) -> dict:
    rag = get_rag()
    if not rag.list_ingested_files():
        raise HTTPException(status_code=400, detail="Please upload at least one document first.")

    # Use provided query or retrieve the last answer from memory
    if request.query:
        answer_data = rag.generate_answer(request.query, request.session_id)
        answer_text = answer_data.get("answer", "")
    else:
        memory_str = rag.format_memory_as_string(request.session_id)
        if not memory_str.strip():
            raise HTTPException(status_code=400, detail="No prior conversation found. Provide a query to generate a video.")
        # Extract the last assistant answer from memory
        lines = memory_str.strip().split("\n")
        answer_text = ""
        for line in reversed(lines):
            if line.startswith("Assistant:"):
                answer_text = line[len("Assistant:") :].strip()
                break
        if not answer_text:
            raise HTTPException(status_code=400, detail="Could not extract an answer from the conversation history.")

    try:
        video_path = get_video_generator().generate(answer_text, request.session_id)
        video_filename = os.path.basename(video_path)
        video_url = f"/videos/{video_filename}"
        return {"video_url": video_url}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
