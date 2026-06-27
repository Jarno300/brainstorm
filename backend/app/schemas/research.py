"""Shared data types for the research pipeline.

Used by both topic_research_service and wikipedia_service to avoid
circular imports between the two modules.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ResearchResult:
    """Parsed research output from Wikipedia or an LLM.

    This is the canonical research data structure consumed by
    build_knowledge_map() and produced by research_topic() /
    page_to_research_result().
    """
    summary: str = ""
    overview: str = ""
    key_concepts: List[dict] = field(default_factory=list)
    use_cases: List[dict] = field(default_factory=list)
    parent_topics: List[dict] = field(default_factory=list)
    child_topics: List[dict] = field(default_factory=list)
    related_topics: List[dict] = field(default_factory=list)
