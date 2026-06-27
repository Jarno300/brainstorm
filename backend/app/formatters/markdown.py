"""
Markdown formatting utilities for the research pipeline.

Converts structured data (ResearchResult, taxonomy dicts) into
markdown documents for library entries. Pure functions — no
side effects, no service dependencies.
"""

from typing import List

from app.schemas.research import ResearchResult


def research_result_to_markdown(
    topic_name: str,
    result: ResearchResult,
    library_content: str = "",
    include_taxonomy: bool = True,
) -> str:
    """Convert a ResearchResult into structured markdown for a library entry.

    Args:
        topic_name: Display name of the topic (e.g., "Quantum computing").
        result: Parsed research output from Wikipedia or an LLM.
        library_content: Optional pre-generated content to prepend.
        include_taxonomy: If True, append ## Parent Topics / ## Child Topics /
                          ## Related Topics sections.

    Returns:
        Markdown string with # title, > summary, ## Overview,
        ## Key Concepts, ## Use Cases, and optional taxonomy sections.
    """
    display = topic_name.replace("-", " ").title()
    lines: List[str] = []

    if library_content.strip():
        lines.append(library_content.strip())
    else:
        # Build from ResearchResult fields
        lines.append(f"# {display}")
        lines.append("")
        if result.summary:
            lines.append(f"> {result.summary}")
            lines.append("")
        if result.overview:
            lines.append("## Overview")
            lines.append("")
            lines.append(result.overview)
            lines.append("")

        if result.key_concepts:
            lines.append("## Key Concepts")
            lines.append("")
            for kc in result.key_concepts:
                name = kc.get("name", "").strip()
                desc = kc.get("description", "").strip()
                lines.append(f"- **{name}**: {desc}")
            lines.append("")

        if result.use_cases:
            lines.append("## Use Cases")
            lines.append("")
            for uc in result.use_cases:
                name = uc.get("name", "").strip()
                desc = uc.get("description", "").strip()
                lines.append(f"- **{name}**: {desc}")
            lines.append("")

    if include_taxonomy:
        taxonomy_md = taxonomy_to_markdown({
            "parent_topics": result.parent_topics,
            "child_topics": result.child_topics,
            "related_topics": result.related_topics,
        })
        if taxonomy_md:
            lines.append("")
            lines.append(taxonomy_md)

    return "\n".join(lines)


def taxonomy_to_markdown(taxonomy: dict) -> str:
    """Convert a taxonomy dict to markdown sections.

    Args:
        taxonomy: Dict with parent_topics, child_topics, related_topics keys,
                  each containing [{"name": str, "description": str}, ...]

    Returns:
        Markdown string with ## Parent Topics, ## Child Topics,
        ## Related Topics sections, or empty string if all empty.
    """
    sections = []
    for key, heading in [
        ("parent_topics", "Parent Topics"),
        ("child_topics", "Child Topics"),
        ("related_topics", "Related Topics"),
    ]:
        items = taxonomy.get(key, [])
        if items:
            lines = [f"## {heading}", ""]
            for item in items:
                name = item.get("name", "unknown")
                desc = item.get("description", "")
                lines.append(f"- {name} - {desc}")
            sections.append("\n".join(lines))
    return "\n\n".join(sections)
