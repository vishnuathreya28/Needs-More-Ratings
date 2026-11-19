"""Offline stand-ins for Grok and the X API, for testing the pipeline without credits or credentials."""
import json
from pathlib import Path

_DIR = Path(__file__).parent


def mock_posts_eligible_response() -> dict:
    """Canned GET /2/notes/search/posts_eligible_for_notes response (raw API shape, so the parser runs)."""
    return json.loads((_DIR / "posts_eligible.json").read_text())


def mock_grok_response(prompt: str) -> dict:
    """Canned Grok JSON answer, picked by the Post ID in the prompt. Unknown posts get NOT ENOUGH EVIDENCE."""
    responses = json.loads((_DIR / "grok_responses.json").read_text())
    for line in prompt.splitlines():
        if line.strip().startswith("Post ID:"):
            post_id = line.split(":", 1)[1].strip()
            if post_id in responses:
                return responses[post_id]
            break
    return {"decision": "NOT ENOUGH EVIDENCE", "note_text": "", "misleading_tags": []}
