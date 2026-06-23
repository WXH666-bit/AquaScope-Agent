from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .schemas import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    SessionCreate,
    SessionUpdate,
)
from .service import ChatService


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ChatService(ROOT)
app = FastAPI(
    title="AquaBio AgentRAG API",
    version="1.0.0",
    description="Local LangGraph, MCP, PDF and multimodal chat backend.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8510"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/system/status")
def system_status() -> dict:
    return SERVICE.status()


@app.post("/api/system/warmup")
def system_warmup() -> dict:
    return SERVICE.warmup()


@app.get("/api/mcp/tools")
def mcp_tools() -> dict:
    return SERVICE.mcp_tools()


@app.get("/api/system/architecture")
def system_architecture() -> dict:
    return SERVICE.architecture()


@app.get("/api/feedback/stats")
def feedback_stats() -> dict:
    return SERVICE.store.feedback_stats()


@app.post("/api/feedback")
def save_feedback(request: FeedbackRequest) -> dict:
    return SERVICE.store.save_feedback(**request.model_dump())


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    try:
        return SERVICE.chat(request)
    except KeyError as error:
        raise HTTPException(404, f"附件不存在：{error}") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/chat/tasks")
def submit_chat_task(request: ChatRequest) -> dict:
    return SERVICE.submit_chat(request)


@app.get("/api/chat/tasks")
def list_chat_tasks() -> list[dict]:
    return SERVICE.chat_tasks()


@app.get("/api/chat/tasks/{task_id}")
def get_chat_task(task_id: str) -> dict:
    try:
        return SERVICE.chat_task(task_id)
    except KeyError as error:
        raise HTTPException(404, "聊天任务不存在") from error


@app.delete("/api/chat/tasks/{task_id}")
def cancel_chat_task(task_id: str) -> dict:
    try:
        return SERVICE.cancel_chat_task(task_id)
    except KeyError as error:
        raise HTTPException(404, "聊天任务不存在") from error


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def events():
        yield "event: node_start\ndata: {\"node\":\"agent\"}\n\n"
        try:
            result = SERVICE.chat(request)
            payload = json.dumps(result, ensure_ascii=False)
            yield f"event: final\ndata: {payload}\n\n"
        except Exception as error:
            payload = json.dumps(
                {"error": str(error)}, ensure_ascii=False
            )
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/uploads/image")
async def upload_image(
    session_id: str = Form(...), file: UploadFile = File(...)
) -> dict:
    try:
        return SERVICE.save_upload(
            session_id,
            file.filename or "image.jpg",
            await file.read(),
            "image",
        )
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/uploads/pdf")
async def upload_pdf(
    session_id: str = Form(...), file: UploadFile = File(...)
) -> dict:
    try:
        return SERVICE.save_upload(
            session_id,
            file.filename or "document.pdf",
            await file.read(),
            "pdf",
        )
    except (ValueError, RuntimeError) as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/sessions")
def create_session(request: SessionCreate) -> dict:
    return SERVICE.store.create_session(request.title, request.session_id)


@app.get("/api/sessions")
def list_sessions(search: str = "") -> list[dict]:
    return SERVICE.store.list_sessions(search)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return SERVICE.store.get_session(session_id)
    except KeyError as error:
        raise HTTPException(404, "会话不存在") from error


@app.patch("/api/sessions/{session_id}")
def update_session(session_id: str, request: SessionUpdate) -> dict:
    try:
        return SERVICE.store.update_session(
            session_id, **request.model_dump()
        )
    except KeyError as error:
        raise HTTPException(404, "会话不存在") from error


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    removed = SERVICE.store.delete_session(session_id)
    SERVICE.conversations.clear(session_id)
    return {"deleted": removed, "session_id": session_id}


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str) -> FileResponse:
    try:
        session = SERVICE.store.get_session(session_id)
    except KeyError as error:
        raise HTTPException(404, "会话不存在") from error
    export_dir = SERVICE.paths.sessions_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"{session_id}.json"
    target.write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return FileResponse(
        target,
        media_type="application/json",
        filename=target.name,
    )


@app.get(
    "/api/sessions/{session_id}/turns/{turn_id}/evidence"
)
def turn_evidence(session_id: str, turn_id: str) -> list[dict]:
    return SERVICE.store.evidence_for_turn(session_id, turn_id)


@app.get("/api/resources/{file_type}")
def list_resources(
    file_type: str, session_id: str | None = None
) -> list[dict]:
    mapping = {"images": "image", "pdfs": "pdf"}
    if file_type not in mapping:
        raise HTTPException(404, "资源类型不存在")
    return SERVICE.store.list_attachments(
        session_id=session_id, file_type=mapping[file_type]
    )


@app.get("/files/{relative_path:path}")
def local_file(relative_path: str) -> FileResponse:
    target = (ROOT / relative_path).resolve()
    if ROOT not in target.parents or not target.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(target)
