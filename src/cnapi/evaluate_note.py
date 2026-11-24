import json
import os

from .xurl_util import run_xurl


def claim_opinion_score(post_id: str, note_text: str) -> float | None:
    """
    Ask X's ClaimOpinion evaluator to score a draft note (POST /2/evaluate_note) without submitting it.
    Higher is better. Returns None in mock mode.
    """
    if os.getenv("MOCK_X_API", "").strip().lower() == "true":
        return None
    payload = {"post_id": str(post_id), "note_text": note_text}
    resp = run_xurl(["xurl", "-X", "POST", "/2/evaluate_note", "-d", json.dumps(payload)])
    return float(resp["data"]["claim_opinion_score"])
