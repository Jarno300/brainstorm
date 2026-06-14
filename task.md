# Implementation Plan: Visual Map Tab

## Backend Changes

1. **backend/app/schemas/topic.py** - Add `source_name` / `target_name` to `TopicEdgeResponse`
2. **backend/app/api/map.py** - Populate edge names; include propositions as suggested topics
3. **backend/app/services/classification_service.py** - Update MAP_PROPOSAL_PROMPT to return `source_topic` (which existing topic each suggestion relates to)
4. **backend/app/tasks/classification_tasks.py** - Create suggestion edges from parent topics to propositions

## Frontend Changes

5. **frontend/src/components/MapTab.jsx** - Complete rewrite using reactflow:
   - Visual canvas with topic nodes and connection lines
   - Solid lines for established topic relationships
   - Dotted/dashed lines for AI-suggested relationships
   - Suggestion nodes styled differently (amber/dashed border)
   - Automatic graph layout (circular/concentric)
   - Pan/zoom controls
