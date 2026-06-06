"""
Prompt templates for memory extraction and merging.

These prompts are the core of the AI engineering in this system.
Each prompt is carefully designed for:
- Precision: Extracting exactly the right information
- Consistency: Producing structured, parseable output
- Robustness: Handling varied transcript styles and content
"""

# ── Memory Extraction Prompt ──────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction engine for a personal knowledge management system.
Your job is to analyze conversation transcripts and extract structured memories.

You MUST return a valid JSON object with the following structure:
{
  "people": [
    {
      "name": "Full Name",
      "slug": "lowercase_underscore_name",
      "facts": [
        {
          "text": "A specific fact about this person",
          "confidence": "high|medium|low",
          "category": "role|background|preference|relationship|skill|opinion"
        }
      ],
      "mentioned_in_context": "Brief description of how they appeared in this conversation"
    }
  ],
  "topics": [
    {
      "name": "Topic or Project Name",
      "slug": "lowercase_underscore_name",
      "category": "project|concept|initiative|tool|process",
      "facts": [
        {"text": "Key fact about this topic", "confidence": "high|medium|low"}
      ],
      "decisions": [
        {"text": "Decision that was made", "date": "YYYY-MM-DD or null", "participants": ["name1"]}
      ],
      "action_items": [
        {"text": "Task description", "assignee": "name or null", "due_date": "YYYY-MM-DD or null", "status": "open"}
      ]
    }
  ],
  "event": {
    "title": "Descriptive event title",
    "date": "YYYY-MM-DD or null",
    "participants": ["name1", "name2"],
    "summary": "2-3 sentence summary of the conversation",
    "key_outcomes": ["outcome1", "outcome2"]
  },
  "relationships": [
    {
      "from_entity": "entity_slug",
      "to_entity": "entity_slug",
      "relationship_type": "works_on|manages|reports_to|collaborates_with|discussed|decided"
    }
  ]
}

Rules:
1. Extract ALL people mentioned, even those referenced indirectly (e.g., "my manager" → infer name from context if possible, otherwise use the reference)
2. Assign a URL-safe slug to each entity: lowercase, underscores, no special chars (e.g., "John Doe" → "john_doe")
3. For each fact, assess confidence:
   - HIGH: explicitly stated in the transcript
   - MEDIUM: strongly implied from context
   - LOW: inferred or speculative
4. Preserve temporal context — extract dates, deadlines, and time references
5. Clearly distinguish between facts, opinions, and decisions
6. Extract relationships between entities (person↔topic, person↔person)
7. If the transcript contains no identifiable people or topics, still create the event entry
8. Keep fact text concise but self-contained (should make sense without the original transcript)"""


def build_extraction_user_prompt(
    transcript_content: str,
    transcript_title: str = "",
    participants_hint: list[str] | None = None,
    occurred_at: str | None = None,
) -> str:
    """Build the user prompt for memory extraction."""
    parts = []

    if transcript_title:
        parts.append(f"Transcript Title: {transcript_title}")
    if occurred_at:
        parts.append(f"Date: {occurred_at}")
    if participants_hint:
        parts.append(f"Known Participants: {', '.join(participants_hint)}")

    parts.append(f"\n--- TRANSCRIPT ---\n{transcript_content}\n--- END TRANSCRIPT ---")
    parts.append("\nExtract all memories from this transcript as a JSON object.")

    return "\n".join(parts)


# ── Memory Merge Prompt ───────────────────────────────────────

MERGE_SYSTEM_PROMPT = """You are a memory file merger for a personal knowledge system.
You will receive an EXISTING memory file (in Markdown with YAML frontmatter) and NEW facts extracted from a recent transcript.
Your job is to produce an UPDATED memory file that intelligently merges the new information.

Rules:
1. PRESERVE all existing information unless explicitly contradicted by newer data
2. When facts conflict, prefer the NEWER information and note the update
3. DEDUPLICATE: do not add facts that are semantically identical to existing ones
4. Maintain chronological order for time-series sections (interactions, events)
5. Keep the same Markdown structure and formatting style as the existing file
6. You MUST return ONLY the complete updated Markdown file content (with YAML frontmatter)
7. Update the frontmatter:
   - Increment the 'version' number
   - Add the new source_transcript ID to the list
   - Update 'updated_at' to the current timestamp
   - Add any new tags
8. For action items: if the new info indicates a task is completed, update its status"""


def build_merge_user_prompt(
    existing_content: str,
    new_facts: dict,
    transcript_id: str,
    current_timestamp: str,
) -> str:
    """Build the user prompt for merging new facts into an existing memory file."""
    import json
    return f"""--- EXISTING MEMORY FILE ---
{existing_content}
--- END EXISTING FILE ---

--- NEW FACTS TO MERGE ---
{json.dumps(new_facts, indent=2)}
--- END NEW FACTS ---

Transcript ID: {transcript_id}
Current Timestamp: {current_timestamp}

Produce the updated memory file with the new information merged in.
Return ONLY the complete Markdown content (including YAML frontmatter).
Do not wrap in code fences."""


# ── File Generation Prompts ───────────────────────────────────

GENERATE_PERSON_PROFILE_PROMPT = """Generate a person profile memory file in Markdown with YAML frontmatter.

The file should follow this exact structure:

---
type: person_profile
entity: {slug}
display_name: "{name}"
created_at: "{timestamp}"
updated_at: "{timestamp}"
source_transcripts: ["{transcript_id}"]
tags: [{tags}]
version: 1
---

# {name}

## Role & Context
(role, company, position — whatever is known)

## Key Facts
- (bullet points of known facts)

## Relationship Notes
- (how you know them, interaction style, etc.)

Use ONLY the facts provided. Do not invent information.
Keep it concise but comprehensive."""


GENERATE_TOPIC_OVERVIEW_PROMPT = """Generate a topic overview memory file in Markdown with YAML frontmatter.

The file should follow this exact structure:

---
type: topic_overview
entity: {slug}
display_name: "{name}"
category: "{category}"
created_at: "{timestamp}"
updated_at: "{timestamp}"
source_transcripts: ["{transcript_id}"]
tags: [{tags}]
version: 1
---

# {name}

## Overview
(what this topic/project is about)

## Key Facts
- (bullet points of known facts)

## Decisions
- (decisions made, with date if known)

## Action Items
- [ ] (open tasks)
- [x] (completed tasks)

Use ONLY the facts provided. Do not invent information."""


GENERATE_EVENT_PROMPT = """Generate an event summary memory file in Markdown with YAML frontmatter.

The file should follow this exact structure:

---
type: event_summary
title: "{title}"
date: "{date}"
participants: [{participants}]
created_at: "{timestamp}"
updated_at: "{timestamp}"
source_transcripts: ["{transcript_id}"]
tags: ["event"]
version: 1
---

# {title}

## Summary
(2-3 sentence overview)

## Participants
- (list of participants)

## Key Outcomes
- (bullet points)

## Notes
(any additional context)

Use ONLY the facts provided. Do not invent information."""
