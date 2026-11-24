import json
import os
import threading

import requests

_usage_lock = threading.Lock()
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "cost_known": True}


def _record_usage(data: dict) -> None:
    """Add this response's token counts and cost (xAI reports cost in 1e-10 USD ticks) to USAGE."""
    usage = data.get("usage") or {}
    ticks = usage.get("cost_in_usd_ticks")
    with _usage_lock:
        USAGE["calls"] += 1
        USAGE["input_tokens"] += usage.get("input_tokens") or 0
        USAGE["output_tokens"] += usage.get("output_tokens") or 0
        if ticks is None:
            USAGE["cost_known"] = False
        else:
            USAGE["cost_usd"] += ticks / 1e10


def _make_request(payload: dict) -> str:
    """
    Call the xAI Responses API and return the output text.
    Currently extremely simple and includes no retry logic.
    """
    responses_url = "https://api.x.ai/v1/responses"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
    }
    response = requests.post(responses_url, headers=headers, json=payload, timeout=300)
    if response.status_code != 200:
        raise Exception(f"Error making request: {response.status_code} {response.text}")
    data = response.json()
    _record_usage(data)
    if data.get("output_text"):
        return data["output_text"]
    return "".join(
        block.get("text", "")
        for item in data.get("output", [])
        if item.get("type") == "message"
        for block in item.get("content", [])
        if block.get("type") == "output_text"
    )


def get_grok_search_json_response(
    prompt: str,
    schema: dict,
    model: str = "grok-4.3",
) -> dict:
    """
    One call that lets Grok search the web and X, and answer with JSON
    matching `schema`.
    Set MOCK_GROK=true to return a canned answer instead (no API call, no credits).
    """
    if os.getenv("MOCK_GROK", "").strip().lower() == "true":
        from mock import mock_grok_response

        return mock_grok_response(prompt)
    payload = {
        "model": model,
        "input": [{"role": "user", "content": prompt}],
        "tools": [
            {"type": "web_search", "enable_image_understanding": True},
            {
                "type": "x_search",
                "enable_image_understanding": True,
                "enable_video_understanding": True,
            },
        ],
        "text": {
            "format": {"type": "json_schema", "name": "note", "schema": schema, "strict": True}
        },
        "store": False,
    }
    return json.loads(_make_request(payload))
