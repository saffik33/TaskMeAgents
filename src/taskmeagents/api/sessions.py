"""Session history REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from taskmeagents.auth.middleware import AuthUser, get_current_user
from taskmeagents.services.agent_factory import get_history_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: str
    user_id: str
    agent_id: str
    status: str
    turn_count: int
    delegation_depth: int


class MessageResponse(BaseModel):
    id: str
    session_id: str
    sequence: int
    role: str
    content: dict
    turn_number: int


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    next_cursor: str | None = None


@router.get("", response_model=SessionListResponse)
async def list_sessions(cursor: str | None = None, limit: int = 20, user: AuthUser = Depends(get_current_user)):
    store = get_history_store()
    sessions, next_cursor = await store.list_user_sessions(user.user_id, cursor, min(limit, 100))
    return SessionListResponse(
        sessions=[SessionResponse(
            id=s.id, user_id=s.user_id, agent_id=s.agent_id, status=s.status,
            turn_count=s.turn_count, delegation_depth=s.delegation_depth,
        ) for s in sessions],
        next_cursor=next_cursor,
    )


# NOTE: /search MUST be defined BEFORE /{session_id} to avoid route shadowing
@router.get("/search", response_model=list[MessageResponse])
async def search_messages(q: str, limit: int = 20, user: AuthUser = Depends(get_current_user)):
    store = get_history_store()
    docs = await store.search_messages(user.user_id, q, min(limit, 100))
    return [MessageResponse(
        id=d.id, session_id=d.session_id, sequence=d.sequence,
        role=d.role, content=d.content, turn_number=d.turn_number,
    ) for d in docs]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, user: AuthUser = Depends(get_current_user)):
    store = get_history_store()
    s = await store.get_session(session_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        id=s.id, user_id=s.user_id, agent_id=s.agent_id, status=s.status,
        turn_count=s.turn_count, delegation_depth=s.delegation_depth,
    )


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(session_id: str, user: AuthUser = Depends(get_current_user)):
    store = get_history_store()
    s = await store.get_session(session_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    docs = await store.get_messages(session_id)
    return [MessageResponse(
        id=d.id, session_id=d.session_id, sequence=d.sequence,
        role=d.role, content=d.content, turn_number=d.turn_number,
    ) for d in docs]
