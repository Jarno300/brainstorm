"""Research endpoint — deep topic research + knowledge map building in one call."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.services.brainstorm_service import get_brainstorm
from app.services.topic_research_service import research_topic, build_knowledge_map
from app.services.realtime_service import publish_brainstorm_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    topic: str


class ResearchResponse(BaseModel):
    status: str
    primary_topic_id: str | None = None
    propositions_created: int = 0


@router.post("/{brainstorm_id}", response_model=ResearchResponse)
def research_brainstorm(
    brainstorm_id: uuid.UUID,
    request: ResearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Research a topic and build the knowledge map for a brainstorm.

    Makes one LLM call that returns a complete structured knowledge map:
    overview, key concepts, use cases, and parent/child/related taxonomy.

    Creates the primary topic card with library entry, and proposition
    cards for taxonomy items on the canvas.
    """
    brainstorm = get_brainstorm(db, brainstorm_id, user_id=current_user.id)
    if not brainstorm:
        raise HTTPException(status_code=404, detail="Brainstorm not found")

    topic_name = request.topic.strip()
    if not topic_name:
        raise HTTPException(status_code=400, detail="Topic name is required")

    # Step 1: Research the topic
    result = research_topic(topic_name, model=brainstorm.model)
    if result is None:
        raise HTTPException(
            status_code=500,
            detail="Research failed. The model could not produce structured results. Try again.",
        )

    # Step 2: Build the knowledge map
    try:
        primary = build_knowledge_map(db, brainstorm_id, topic_name, result, commit=True)
    except Exception as e:
        logger.error("build_knowledge_map error | brainstorm=%s error=%s", brainstorm_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to build knowledge map: {e}")

    # Step 3: Notify frontend via WebSocket
    props_count = sum(1 for _ in [
        result.parent_topics, result.child_topics, result.related_topics
    ])
    publish_brainstorm_event(
        "classification_complete",
        brainstorm_id,
        {
            "status": "success",
            "topics_created": 1,
            "primary_topic": {
                "id": str(primary.id),
                "name": primary.name,
            },
        },
    )

    logger.info(
        "research done | brainstorm=%s topic=%s",
        brainstorm_id, topic_name,
    )

    return ResearchResponse(
        status="success",
        primary_topic_id=str(primary.id),
        propositions_created=props_count,
    )
