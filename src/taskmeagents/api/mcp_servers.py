"""MCP server management REST endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmeagents.auth.middleware import AuthUser, get_current_user
from taskmeagents.database import get_db
from taskmeagents.mcp.registry import get_mcp_registry
from taskmeagents.models.mcp_server import McpServerConfig
from taskmeagents.schemas.mcp import McpServerCreate, McpServerResponse, McpServerUpdate, McpTestResult

router = APIRouter(prefix="/api/mcp-servers", tags=["mcp-servers"])


def _row_to_response(row: McpServerConfig) -> McpServerResponse:
    return McpServerResponse(
        mcp_server_id=str(row.mcp_server_id), name=row.name, description=row.description,
        host=row.host, port=row.port, path=row.path, use_tls=row.use_tls,
        auth_strategy=row.auth_strategy, headers=row.headers or {}, auto_approve=row.auto_approve,
        passthrough_headers=row.passthrough_headers or [], included_tools=row.included_tools or {},
        created_at=row.created_at, updated_at=row.updated_at, updated_by=row.updated_by,
    )


@router.get("", response_model=list[McpServerResponse])
async def list_servers(db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(McpServerConfig).order_by(McpServerConfig.name))
    return [_row_to_response(r) for r in result.scalars().all()]


@router.get("/{server_id}", response_model=McpServerResponse)
async def get_server(server_id: str, db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(McpServerConfig).where(McpServerConfig.mcp_server_id == server_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return _row_to_response(row)


@router.post("", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(body: McpServerCreate, db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    server = McpServerConfig(
        mcp_server_id=uuid.uuid4(), name=body.name, description=body.description,
        host=body.host, port=body.port, path=body.path, use_tls=body.use_tls,
        auth_strategy=body.auth_strategy, headers=body.headers, auto_approve=body.auto_approve,
        passthrough_headers=body.passthrough_headers, included_tools=body.included_tools,
        updated_by=user.user_id,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return _row_to_response(server)


@router.put("/{server_id}", response_model=McpServerResponse)
async def update_server(server_id: str, body: McpServerUpdate, db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(McpServerConfig).where(McpServerConfig.mcp_server_id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(server, field, value)
    server.updated_by = user.user_id
    server.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(server)
    get_mcp_registry().invalidate_server(server_id)
    return _row_to_response(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str, db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(McpServerConfig).where(McpServerConfig.mcp_server_id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await db.delete(server)
    await db.commit()
    get_mcp_registry().invalidate_server(server_id)


@router.post("/{server_id}/test", response_model=McpTestResult)
async def test_connection(server_id: str, db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(McpServerConfig).where(McpServerConfig.mcp_server_id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    try:
        registry = get_mcp_registry()
        entry = await registry.get_server(str(server.mcp_server_id))
        return McpTestResult(connected=True, tools=entry.tools)
    except Exception as e:
        return McpTestResult(connected=False, error=str(e))
