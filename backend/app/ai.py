from fastapi import HTTPException
from openai import OpenAI

from .config import settings
from .models import Sprint, Story


def _story_line(story: Story) -> str:
    points = f", {story.story_points} pts" if story.story_points else ""
    assignee = f", assignee {story.assignee_id}" if story.assignee_id else ""
    blockers = ", ".join(link.blocker_story_id for link in story.blocked_by_links) or "none"
    return f"- {story.title} ({story.id}): {story.status}{points}{assignee}; blockers: {blockers}"


def generate_sprint_report(sprint: Sprint, stories: list[Story], additional_context: str = "") -> str:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI is not configured. Set OPENAI_API_KEY in backend/.env and restart the API.",
        )

    client = OpenAI(api_key=settings.openai_api_key)
    story_block = "\n".join(_story_line(story) for story in stories) or "No stories were assigned to this sprint."
    prompt = f"""
Draft a concise sprint report in Markdown for a software project manager.

Use only the supplied sprint data. Do not invent work, people, blockers, dates, metrics, or next steps.

Sprint:
- Name: {sprint.name}
- Goal: {sprint.goal or "No sprint goal recorded"}
- Status: {sprint.status}
- Velocity: {sprint.velocity if sprint.velocity is not None else "not calculated"}
- Notes: {sprint.notes or "No closing notes"}

Stories:
{story_block}

Additional context from the manager:
{additional_context or "None"}

Include these sections:
## Sprint Summary
## Completed Work
## Incomplete Work
## Blockers and Risks
## Suggested Next Sprint Focus
"""
    response = client.responses.create(
        model=settings.openai_model,
        input=prompt,
    )
    text = getattr(response, "output_text", None)
    if not text:
        raise HTTPException(status_code=502, detail="AI provider returned an empty sprint report")
    return text
