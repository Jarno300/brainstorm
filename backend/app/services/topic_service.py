import uuid
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.models.topic_edge import TopicEdge


def normalize_topic_name(name: str) -> str:
    return " ".join(str(name or "").lower().replace("-", " ").split())


def _normalized_name_expr():
    """SQL expression that normalizes topic.name the same way Python does."""
    return func.lower(func.replace(Topic.name, "-", " "))


def create_topic(
    db: Session,
    brainstorm_id: uuid.UUID,
    name: str,
    description: str = "",
    library_path: str = "",
    is_proposition: bool = False,
    confidence: float = 0.0,
    outline: Optional[list] = None,
    commit: bool = True,
) -> Topic:
    topic = Topic(
        brainstorm_id=brainstorm_id,
        name=name,
        description=description,
        library_path=library_path,
        is_proposition=is_proposition,
        confidence=confidence,
        outline=outline,
    )
    db.add(topic)
    if commit:
        db.commit()
        db.refresh(topic)
    else:
        db.flush()
    return topic


def get_topics(db: Session, brainstorm_id: uuid.UUID) -> List[Topic]:
    return db.query(Topic).filter(Topic.brainstorm_id == brainstorm_id).all()


def get_topic(db: Session, topic_id: uuid.UUID) -> Optional[Topic]:
    return db.query(Topic).filter(Topic.id == topic_id).first()


def get_topic_by_name(
    db: Session,
    brainstorm_id: uuid.UUID,
    name: str,
    is_proposition: Optional[bool] = None,
) -> Optional[Topic]:
    """Find a topic by normalized name using SQL-level comparison.

    Avoids loading all topics into memory by pushing the normalization
    to the database via func.lower / func.replace.
    """
    normalized_name = normalize_topic_name(name)
    query = db.query(Topic).filter(
        Topic.brainstorm_id == brainstorm_id,
        _normalized_name_expr() == normalized_name,
    )

    if is_proposition is not None:
        query = query.filter(Topic.is_proposition == is_proposition)

    return query.first()


def create_edge(
    db: Session,
    brainstorm_id: uuid.UUID,
    source_topic_id: uuid.UUID,
    target_topic_id: uuid.UUID,
    relationship: str = "related",
    weight: float = 1.0,
    commit: bool = True,
) -> TopicEdge:
    edge = TopicEdge(
        brainstorm_id=brainstorm_id,
        source_topic_id=source_topic_id,
        target_topic_id=target_topic_id,
        relationship=relationship,
        weight=weight,
    )
    db.add(edge)
    if commit:
        db.commit()
        db.refresh(edge)
    else:
        db.flush()
    return edge


def get_edges(db: Session, brainstorm_id: uuid.UUID) -> List[TopicEdge]:
    return db.query(TopicEdge).filter(TopicEdge.brainstorm_id == brainstorm_id).all()


def get_edge_between(
    db: Session,
    brainstorm_id: uuid.UUID,
    source_topic_id: uuid.UUID,
    target_topic_id: uuid.UUID,
) -> Optional[TopicEdge]:
    """Find an edge between two topics in either direction."""
    return db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        TopicEdge.source_topic_id == source_topic_id,
        TopicEdge.target_topic_id == target_topic_id,
    ).first()


def delete_propositions(db: Session, brainstorm_id: uuid.UUID, commit: bool = True):
    db.query(Topic).filter(
        Topic.brainstorm_id == brainstorm_id,
        Topic.is_proposition == True,
    ).delete(synchronize_session=False)
    if commit:
        db.commit()


def promote_topic_to_main(
    db: Session,
    topic: Topic,
    confidence: Optional[float] = None,
    library_path: str = "",
    commit: bool = True,
) -> Topic:
    topic.is_proposition = False
    if confidence is not None:
        topic.confidence = confidence
    if library_path:
        topic.library_path = library_path
    if commit:
        db.commit()
        db.refresh(topic)
    return topic


def promote_suggestion_edges_to_related(
    db: Session,
    brainstorm_id: uuid.UUID,
    target_topic_id: uuid.UUID,
    commit: bool = True,
) -> int:
    updated = db.query(TopicEdge).filter(
        TopicEdge.brainstorm_id == brainstorm_id,
        TopicEdge.target_topic_id == target_topic_id,
        TopicEdge.relationship == "suggestion",
    ).update({"relationship": "related"}, synchronize_session=False)
    if commit:
        db.commit()
    return updated
