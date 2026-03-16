"""PostgreSQL implementation of HistoryStore.

Translated from go_companion/internal/history/mongo_store.go
Uses INSERT ON CONFLICT DO NOTHING for idempotent message writes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from taskmeagents.conversation.types import Attachment
from taskmeagents.history import attachments as att_storage
from taskmeagents.history.store import HistoryStore, MessageDocument, SessionData, WriteResult
from taskmeagents.models.message import Message as MessageModel
from taskmeagents.models.session import Session as SessionModel


class PostgresHistoryStore(HistoryStore):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def upsert_session(self, session: SessionData) -> None:
        async with self._session_factory() as db:
            stmt = insert(SessionModel).values(
                id=session.id,
                user_id=session.user_id,
                agent_id=session.agent_id,
                parent_session_id=session.parent_session_id,
                status=session.status,
                delegation_depth=session.delegation_depth,
            )
            update_dict: dict = {
                "status": session.status,
                "last_activity_at": datetime.now(timezone.utc),
            }
            if session.turn_count > 0:
                update_dict["turn_count"] = session.turn_count
            if session.message_count_delta > 0:
                update_dict["message_count"] = SessionModel.message_count + session.message_count_delta
            if session.token_usage_delta:
                # Merge token usage via jsonb || operator
                update_dict["token_usage"] = text(
                    "sessions.token_usage || :usage_delta::jsonb"
                ).bindparams(
                    usage_delta=json.dumps({
                        "input_tokens": session.token_usage_delta.input_tokens,
                        "output_tokens": session.token_usage_delta.output_tokens,
                        "cache_read_tokens": session.token_usage_delta.cache_read_tokens,
                        "cache_write_tokens": session.token_usage_delta.cache_write_tokens,
                    })
                )
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_dict)
            await db.execute(stmt)
            await db.commit()

    async def write_messages(self, messages: list[MessageDocument]) -> list[WriteResult]:
        if not messages:
            return []
        async with self._session_factory() as db:
            results = []
            for msg in messages:
                stmt = insert(MessageModel).values(
                    id=msg.id,
                    session_id=msg.session_id,
                    sequence=msg.sequence,
                    role=msg.role,
                    content=msg.content,
                    turn_number=msg.turn_number,
                ).on_conflict_do_nothing(index_elements=["id"])
                result = await db.execute(stmt)
                results.append(WriteResult(message_id=msg.id, inserted=result.rowcount > 0))
            await db.commit()
            return results

    async def persist_batch(self, session: SessionData, messages: list[MessageDocument]) -> list[WriteResult]:
        """Atomic session upsert + message writes in a single transaction."""
        async with self._session_factory() as db:
            async with db.begin():
                # Upsert session
                session_stmt = insert(SessionModel).values(
                    id=session.id,
                    user_id=session.user_id,
                    agent_id=session.agent_id,
                    parent_session_id=session.parent_session_id,
                    status=session.status,
                    delegation_depth=session.delegation_depth,
                )
                update_dict: dict = {
                    "status": session.status,
                    "last_activity_at": datetime.now(timezone.utc),
                }
                if session.turn_count > 0:
                    update_dict["turn_count"] = session.turn_count
                if session.message_count_delta > 0:
                    update_dict["message_count"] = SessionModel.message_count + session.message_count_delta
                session_stmt = session_stmt.on_conflict_do_update(index_elements=["id"], set_=update_dict)
                await db.execute(session_stmt)

                # Write messages (idempotent)
                results = []
                for msg in messages:
                    msg_stmt = insert(MessageModel).values(
                        id=msg.id,
                        session_id=msg.session_id,
                        sequence=msg.sequence,
                        role=msg.role,
                        content=msg.content,
                        turn_number=msg.turn_number,
                    ).on_conflict_do_nothing(index_elements=["id"])
                    result = await db.execute(msg_stmt)
                    results.append(WriteResult(message_id=msg.id, inserted=result.rowcount > 0))
                return results

    async def get_messages(self, session_id: str, include_attachments: bool = False) -> list[MessageDocument]:
        async with self._session_factory() as db:
            result = await db.execute(
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.sequence)
            )
            rows = result.scalars().all()
            docs = [
                MessageDocument(
                    id=row.id,
                    session_id=str(row.session_id),
                    sequence=row.sequence,
                    role=row.role,
                    content=row.content,
                    turn_number=row.turn_number,
                    created_at=row.created_at,
                )
                for row in rows
            ]
            return docs

    async def list_user_sessions(
        self, user_id: str, cursor: str | None = None, limit: int = 20
    ) -> tuple[list[SessionData], str | None]:
        async with self._session_factory() as db:
            query = (
                select(SessionModel)
                .where(SessionModel.user_id == user_id)
                .order_by(SessionModel.last_activity_at.desc(), SessionModel.id)
                .limit(limit + 1)
            )
            if cursor:
                # Keyset pagination: cursor is ISO timestamp of last_activity_at
                query = query.where(SessionModel.last_activity_at < cursor)

            result = await db.execute(query)
            rows = result.scalars().all()

            sessions = [
                SessionData(
                    id=str(row.id),
                    user_id=row.user_id,
                    agent_id=row.agent_id,
                    parent_session_id=str(row.parent_session_id) if row.parent_session_id else None,
                    status=row.status,
                    message_count_delta=0,
                    turn_count=row.turn_count,
                    last_activity_at=row.last_activity_at,
                    delegation_depth=row.delegation_depth,
                )
                for row in rows[:limit]
            ]
            next_cursor = None
            if len(rows) > limit:
                next_cursor = rows[limit - 1].last_activity_at.isoformat()
            return sessions, next_cursor

    async def search_messages(self, user_id: str, query: str, limit: int = 20) -> list[MessageDocument]:
        async with self._session_factory() as db:
            # Use PostgreSQL jsonb content search
            result = await db.execute(
                text("""
                    SELECT m.* FROM messages m
                    JOIN sessions s ON s.id = m.session_id
                    WHERE s.user_id = :user_id
                    AND m.content::text ILIKE :query
                    ORDER BY m.created_at DESC
                    LIMIT :limit
                """),
                {"user_id": user_id, "query": f"%{query}%", "limit": limit},
            )
            rows = result.mappings().all()
            return [
                MessageDocument(
                    id=row["id"],
                    session_id=str(row["session_id"]),
                    sequence=row["sequence"],
                    role=row["role"],
                    content=row["content"],
                    turn_number=row["turn_number"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    async def get_session(self, session_id: str) -> SessionData | None:
        async with self._session_factory() as db:
            result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
            row = result.scalar_one_or_none()
            if not row:
                return None
            return SessionData(
                id=str(row.id),
                user_id=row.user_id,
                agent_id=row.agent_id,
                parent_session_id=str(row.parent_session_id) if row.parent_session_id else None,
                status=row.status,
                turn_count=row.turn_count,
                last_activity_at=row.last_activity_at,
                delegation_depth=row.delegation_depth,
            )

    async def update_message(self, message: MessageDocument) -> None:
        async with self._session_factory() as db:
            await db.execute(
                update(MessageModel)
                .where(MessageModel.id == message.id)
                .values(content=message.content)
            )
            await db.commit()

    async def upload_and_strip_attachments(
        self, user_id: str, session_id: str, message_id: str, attachments: list[Attachment]
    ) -> None:
        await att_storage.upload_and_strip(user_id, session_id, message_id, attachments)

    async def rehydrate_attachments(
        self, user_id: str, session_id: str, message_id: str, attachments: list[Attachment]
    ) -> None:
        await att_storage.rehydrate(user_id, session_id, message_id, attachments)

    async def close(self) -> None:
        pass  # Session factory manages connection lifecycle
