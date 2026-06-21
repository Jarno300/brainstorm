"""
Gap detection service — analyzes the knowledge graph for structural gaps
and suggests what to explore next.

Detects:
  1. Orphan topics (no edges at all)
  2. Pendant topics (only one edge — poorly connected)
  3. Disconnected clusters (groups with no inter-group edges)
  4. Missing taxonomy dimensions (no parents, children, or related topics)
"""

import logging
import uuid
from collections import deque
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.models.topic_edge import TopicEdge
from app.services.topic_service import get_topics, get_edges

logger = logging.getLogger(__name__)

# ─── Gap types ────────────────────────────────────────────────

GAP_ORPHAN = "orphan"
GAP_PENDANT = "pendant"
GAP_DISCONNECTED_CLUSTER = "disconnected_cluster"
GAP_MISSING_PARENTS = "missing_parents"
GAP_MISSING_CHILDREN = "missing_children"
GAP_MISSING_RELATED = "missing_related"


def _build_adjacency(
    topics: List[Topic], edges: List[TopicEdge]
) -> dict[uuid.UUID, set[uuid.UUID]]:
    """Build undirected adjacency map: topic_id → set of neighbor topic_ids."""
    adj: dict[uuid.UUID, set[uuid.UUID]] = {t.id: set() for t in topics}
    for e in edges:
        if e.source_topic_id in adj and e.target_topic_id in adj:
            adj[e.source_topic_id].add(e.target_topic_id)
            adj[e.target_topic_id].add(e.source_topic_id)
    return adj


def _find_clusters(
    topic_ids: set[uuid.UUID], adj: dict[uuid.UUID, set[uuid.UUID]]
) -> List[set[uuid.UUID]]:
    """Find connected components (clusters) using BFS."""
    visited: set[uuid.UUID] = set()
    clusters: List[set[uuid.UUID]] = []

    for tid in topic_ids:
        if tid in visited:
            continue
        cluster: set[uuid.UUID] = set()
        queue = deque([tid])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            cluster.add(node)
            for neighbor in adj.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        clusters.append(cluster)

    return clusters


def _get_taxonomy_gaps(topic: Topic) -> List[dict]:
    """Check a topic's taxonomy for missing dimensions."""
    gaps = []
    display = topic.name.replace("-", " ").title()

    if not topic.taxonomy or not isinstance(topic.taxonomy, dict):
        # No taxonomy stored — suggest generating one
        gaps.append({
            "type": GAP_MISSING_RELATED,
            "topic_id": str(topic.id),
            "topic_name": topic.name,
            "message": f'"{display}" has no related topics yet. Explore it to discover connections.',
            "action": "explore",
        })
        return gaps

    tax = topic.taxonomy
    if not tax.get("parent_topics"):
        gaps.append({
            "type": GAP_MISSING_PARENTS,
            "topic_id": str(topic.id),
            "topic_name": topic.name,
            "message": f'"{display}" has no parent topics. What broader field does it belong to?',
            "action": "research",
        })
    if not tax.get("child_topics"):
        gaps.append({
            "type": GAP_MISSING_CHILDREN,
            "topic_id": str(topic.id),
            "topic_name": topic.name,
            "message": f'"{display}" has no sub-topics. What are its key components?',
            "action": "research",
        })
    if not tax.get("related_topics"):
        gaps.append({
            "type": GAP_MISSING_RELATED,
            "topic_id": str(topic.id),
            "topic_name": topic.name,
            "message": f'"{display}" has no related topics. What fields does it connect to?',
            "action": "research",
        })

    return gaps


def detect_gaps(
    db: Session, brainstorm_id: uuid.UUID
) -> List[dict]:
    """Analyze the knowledge graph and return a list of gap suggestions.

    Each gap is a dict with:
      - type: one of the GAP_* constants
      - topic_id / topic_name: the topic(s) involved
      - message: human-readable suggestion
      - action: 'explore', 'research', 'connect', or 'bridge'
    """
    topics = [t for t in get_topics(db, brainstorm_id) if not t.is_proposition]
    edges = get_edges(db, brainstorm_id)
    # Filter to non-suggestion edges only
    real_edges = [e for e in edges if not e.relationship.startswith("suggestion")]

    if not topics:
        return [{
            "type": "empty_map",
            "topic_id": None,
            "topic_name": None,
            "message": "Your map is empty. Start by researching a topic or chatting with the AI.",
            "action": "research",
        }]

    topic_map = {t.id: t for t in topics}
    adj = _build_adjacency(topics, real_edges)
    gaps: List[dict] = []

    # 1. Detect orphans (no edges at all)
    for tid, neighbors in adj.items():
        if len(neighbors) == 0:
            topic = topic_map[tid]
            gaps.append({
                "type": GAP_ORPHAN,
                "topic_id": str(tid),
                "topic_name": topic.name,
                "message": (
                    f'"{topic.name.replace("-", " ").title()}" is disconnected from everything. '
                    "Connect it to related topics or explore it to generate suggestions."
                ),
                "action": "explore",
            })

    # 2. Detect pendant topics (single edge — fragile connection)
    if len(topics) >= 3:
        for tid, neighbors in adj.items():
            if len(neighbors) == 1:
                topic = topic_map[tid]
                neighbor = topic_map.get(next(iter(neighbors)))
                if neighbor:
                    gaps.append({
                        "type": GAP_PENDANT,
                        "topic_id": str(tid),
                        "topic_name": topic.name,
                        "message": (
                            f'"{topic.name.replace("-", " ").title()}" is only connected to '
                            f'"{neighbor.name.replace("-", " ").title()}". '
                            "Add more connections to strengthen the map."
                        ),
                        "action": "connect",
                    })

    # 3. Detect disconnected clusters (≥2 groups with no inter-group edges)
    topic_ids = {t.id for t in topics}
    clusters = _find_clusters(topic_ids, adj)
    if len(clusters) >= 2:
        # For each pair of clusters, suggest a bridge
        for i, c1 in enumerate(clusters):
            for j, c2 in enumerate(clusters):
                if j <= i:
                    continue
                # Pick the highest-confidence topic from each cluster
                t1 = max((topic_map[tid] for tid in c1), key=lambda t: t.confidence or 0)
                t2 = max((topic_map[tid] for tid in c2), key=lambda t: t.confidence or 0)
                gaps.append({
                    "type": GAP_DISCONNECTED_CLUSTER,
                    "topic_id": str(t1.id),
                    "topic_name": t1.name,
                    "related_topic_id": str(t2.id),
                    "related_topic_name": t2.name,
                    "message": (
                        f'"{t1.name.replace("-", " ").title()}" and '
                        f'"{t2.name.replace("-", " ").title()}" are in separate clusters. '
                        "Explore their connection to bridge these knowledge groups."
                    ),
                    "action": "bridge",
                })

    # 4. Taxonomy gaps (missing parent/child/related)
    for topic in topics:
        tax_gaps = _get_taxonomy_gaps(topic)
        gaps.extend(tax_gaps)

    # Sort: structural gaps first, then taxonomy gaps
    priority_order = {
        GAP_ORPHAN: 0,
        GAP_DISCONNECTED_CLUSTER: 1,
        GAP_PENDANT: 2,
        GAP_MISSING_PARENTS: 3,
        GAP_MISSING_CHILDREN: 4,
        GAP_MISSING_RELATED: 5,
    }
    gaps.sort(key=lambda g: priority_order.get(g["type"], 99))

    logger.debug(
        "gap_detection done | brainstorm=%s topics=%d edges=%d clusters=%d gaps=%d",
        brainstorm_id, len(topics), len(real_edges), len(clusters), len(gaps),
    )

    return gaps
