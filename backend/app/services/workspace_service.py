import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ChatMessage,
    Document,
    SourceReference,
    User,
    VectorStore,
    WorkspaceSession,
)

logger = logging.getLogger(__name__)


class WorkspaceService:
    """
    Service handling workspace session lifecycle, document metadata persistence,
    vector store registration, chat message logging, and source citation tracking.
    All methods include fallback exception handling for database resilience.
    """

    @staticmethod
    async def create_session(
        db: AsyncSession,
        title: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None
    ) -> Optional[WorkspaceSession]:
        """
        Creates a new WorkspaceSession. Supports anonymous usage (user_id=None).
        """
        try:
            session_title = title.strip() if title and title.strip() else "Untitled Workspace Session"
            session = WorkspaceSession(
                user_id=user_id,
                title=session_title
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            logger.info(f"WorkspaceService: Created session '{session.id}' with title '{session.title}'")
            return session
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to create session: {e}", exc_info=True)
            await db.rollback()
            return None

    @staticmethod
    async def get_session(
        db: AsyncSession,
        session_id: uuid.UUID
    ) -> Optional[WorkspaceSession]:
        """
        Retrieves a session by ID including documents, vector stores, chat messages, and sources.
        """
        try:
            stmt = (
                select(WorkspaceSession)
                .where(WorkspaceSession.id == session_id)
                .options(
                    selectinload(WorkspaceSession.documents).selectinload(Document.vector_stores),
                    selectinload(WorkspaceSession.chat_messages).selectinload(ChatMessage.sources)
                )
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to retrieve session '{session_id}': {e}", exc_info=True)
            return None

    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[WorkspaceSession]:
        """
        Lists workspace sessions ordered by update time descending.
        """
        try:
            stmt = select(WorkspaceSession).order_by(WorkspaceSession.updated_at.desc()).offset(offset).limit(limit)
            if user_id:
                stmt = stmt.where(WorkspaceSession.user_id == user_id)
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to list sessions: {e}", exc_info=True)
            return []

    @staticmethod
    async def update_session_title(
        db: AsyncSession,
        session_id: uuid.UUID,
        title: str
    ) -> Optional[WorkspaceSession]:
        """
        Updates the title of a workspace session.
        """
        try:
            session = await WorkspaceService.get_session(db, session_id)
            if not session:
                return None
            session.title = title.strip()
            await db.commit()
            await db.refresh(session)
            logger.info(f"WorkspaceService: Updated title for session '{session_id}' to '{session.title}'")
            return session
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to update session title for '{session_id}': {e}", exc_info=True)
            await db.rollback()
            return None

    @staticmethod
    async def delete_session(
        db: AsyncSession,
        session_id: uuid.UUID
    ) -> bool:
        """
        Deletes a workspace session and cascades deletion to documents and chat history.
        """
        try:
            session = await db.get(WorkspaceSession, session_id)
            if not session:
                return False
            await db.delete(session)
            await db.commit()
            logger.info(f"WorkspaceService: Deleted session '{session_id}'")
            return True
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to delete session '{session_id}': {e}", exc_info=True)
            await db.rollback()
            return False

    @staticmethod
    async def persist_document(
        db: AsyncSession,
        filename: str,
        original_source: str,
        media_type: str,
        file_path: str,
        status: str = "uploaded",
        session_id: Optional[uuid.UUID] = None
    ) -> Optional[Document]:
        """
        Persists document file metadata in PostgreSQL.
        """
        try:
            doc = Document(
                session_id=session_id,
                filename=filename,
                original_source=original_source,
                media_type=media_type,
                file_path=file_path,
                status=status
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            logger.info(f"WorkspaceService: Persisted document metadata '{doc.id}' ({filename})")
            return doc
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to persist document metadata: {e}", exc_info=True)
            await db.rollback()
            return None

    @staticmethod
    async def persist_vector_store(
        db: AsyncSession,
        index_path: str,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        chunk_count: int = 0,
        document_id: Optional[uuid.UUID] = None
    ) -> Optional[VectorStore]:
        """
        Persists vector store disk index pointer metadata in PostgreSQL.
        """
        try:
            vs = VectorStore(
                document_id=document_id,
                index_path=index_path,
                embedding_model=embedding_model,
                chunk_count=chunk_count
            )
            db.add(vs)
            await db.commit()
            await db.refresh(vs)
            logger.info(f"WorkspaceService: Persisted vector store metadata '{vs.id}' (path: '{index_path}')")
            return vs
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to persist vector store metadata: {e}", exc_info=True)
            await db.rollback()
            return None

    @staticmethod
    async def persist_chat_message(
        db: AsyncSession,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[ChatMessage]:
        """
        Persists a conversational message turn and optional source citations in PostgreSQL.
        """
        try:
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=content
            )
            db.add(msg)
            await db.flush()  # Generate msg.id for source foreign keys

            if sources:
                for src_data in sources:
                    doc_id = src_data.get("document_id")
                    if isinstance(doc_id, str):
                        try:
                            doc_id = uuid.UUID(doc_id)
                        except ValueError:
                            doc_id = None

                    source_ref = SourceReference(
                        message_id=msg.id,
                        document_id=doc_id,
                        source_type=src_data.get("source_type", "document_chunk"),
                        locator=str(src_data.get("locator", src_data.get("page", "unknown"))),
                        metadata_json={
                            k: v for k, v in src_data.items()
                            if k not in ("source_type", "locator", "document_id")
                        }
                    )
                    db.add(source_ref)

            await db.commit()
            await db.refresh(msg)
            logger.info(f"WorkspaceService: Persisted chat message '{msg.id}' for session '{session_id}'")
            return msg
        except Exception as e:
            logger.error(f"WorkspaceService: Failed to persist chat message: {e}", exc_info=True)
            await db.rollback()
            return None
