"""Research endpoint — deep topic research + knowledge map building in one call.

Offloads the LLM call to a Celery task so the request returns immediately.
Results are published via WebSocket (classification_complete event).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.services.brainstorm_service import get_brainstorm
from app.tasks.research_tasks import process_research, process_research_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    topic: str


@router.post("/{brainstorm_id}", status_code=202)
def research_brainstorm(
    brainstorm_id: uuid.UUID,
    request: ResearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Research a topic and build the knowledge map for a brainstorm.

    Dispatches the research to a Celery task and returns 202 Accepted
    immediately. The LLM call and knowledge map building happen in the
    background. Results are published via WebSocket
    (classification_complete event) when ready.

    Falls back to synchronous execution if Celery/Redis is unavailable.
    """
    brainstorm = get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic_name = request.topic.strip()
    if not topic_name:
        raise HTTPException(status_code=400, detail="Topic name is required")

    # Dispatch to Celery — returns immediately, results via WebSocket
    try:
        process_research.delay(str(brainstorm_id), topic_name)
        logger.info("research dispatched | brainstorm=%s topic=%s", brainstorm_id, topic_name)
    except Exception as e:
        logger.warning("Celery dispatch failed, running research synchronously: %s", e)
        try:
            result = process_research_sync(str(brainstorm_id), topic_name)
            if result.get("status") == "error":
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Research failed"),
                )
        except HTTPException:
            raise
        except Exception as sync_e:
            logger.error("Synchronous research also failed: %s", sync_e)
            raise HTTPException(
                status_code=500,
                detail="Research failed. The model could not produce structured results. Try again.",
            )

    return JSONResponse(
        status_code=202,
        content={"status": "processing", "topic": topic_name},
    )
