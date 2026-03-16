"""Agent management REST endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmeagents.auth.middleware import AuthUser, get_current_user
from taskmeagents.database import get_db
from taskmeagents.models.agent import Agent, AgentVersion
from taskmeagents.schemas.agent import AgentCreate, AgentResponse, AgentUpdate, AgentVersionResponse, RollbackRequest
from taskmeagents.services.agent_factory import get_agent_factory

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _agent_to_response(row: Agent) -> AgentResponse:
    return AgentResponse(
        agent_id=row.agent_id, name=row.name, system_prompt=row.system_prompt, model=row.model,
        max_tokens=row.max_tokens, temperature=row.temperature, client_tools=row.client_tools or [],
        mcp_server_ids=row.mcp_server_ids or [], sub_agents=row.sub_agents or [],
        use_prompt_cache=row.use_prompt_cache, thinking=row.thinking or {},
        observation_masking=row.observation_masking, tool=row.tool,
        version=row.version, version_comment=row.version_comment, updated_by=row.updated_by,
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(Agent).order_by(Agent.name))
    return [_agent_to_response(r) for r in result.scalars().all()]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_response(row)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    existing = await db.execute(select(Agent).where(Agent.agent_id == body.agent_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent already exists")
    agent = Agent(
        agent_id=body.agent_id, name=body.name, system_prompt=body.system_prompt, model=body.model,
        max_tokens=body.max_tokens, temperature=body.temperature, client_tools=body.client_tools,
        mcp_server_ids=body.mcp_server_ids, sub_agents=body.sub_agents,
        use_prompt_cache=body.use_prompt_cache, thinking=body.thinking,
        observation_masking=body.observation_masking or {"enabled": True, "recent_window_turns": 3},
        tool=body.tool, version_comment=body.version_comment, updated_by=user.user_id,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return _agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, body: AgentUpdate, db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Archive current version
    archive = AgentVersion(agent_id=agent_id, version=agent.version, config={
        "agent_id": agent.agent_id, "name": agent.name, "system_prompt": agent.system_prompt,
        "model": agent.model, "max_tokens": agent.max_tokens, "temperature": agent.temperature,
        "version": agent.version, "version_comment": agent.version_comment,
    })
    db.add(archive)
    # Apply updates
    for field, value in body.model_dump(exclude_unset=True).items():
        if field != "version_comment":
            setattr(agent, field, value)
    agent.version += 1
    agent.version_comment = body.version_comment
    agent.updated_by = user.user_id
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    get_agent_factory().invalidate(agent_id)
    return _agent_to_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
    get_agent_factory().invalidate(agent_id)


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def list_versions(agent_id: str, db: AsyncSession = Depends(get_db), _: AuthUser = Depends(get_current_user)):
    result = await db.execute(
        select(AgentVersion).where(AgentVersion.agent_id == agent_id).order_by(AgentVersion.version.desc())
    )
    return [AgentVersionResponse(agent_id=r.agent_id, version=r.version, config=r.config, archived_at=r.archived_at) for r in result.scalars().all()]


@router.post("/{agent_id}/rollback", response_model=AgentResponse)
async def rollback_agent(agent_id: str, body: RollbackRequest, db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    version_result = await db.execute(
        select(AgentVersion).where(AgentVersion.agent_id == agent_id, AgentVersion.version == body.version)
    )
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    config = version.config
    for key, value in config.items():
        if key not in ("agent_id", "version", "version_comment") and hasattr(agent, key):
            setattr(agent, key, value)
    agent.version += 1
    agent.version_comment = f"Rolled back to version {body.version}"
    agent.updated_by = user.user_id
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    get_agent_factory().invalidate(agent_id)
    return _agent_to_response(agent)
