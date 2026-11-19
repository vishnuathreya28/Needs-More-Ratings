"""
Check notes against the platform limits and the starter prompt's rules, offline, before submitting.

  uv run src/validate_note.py --file notes.jsonl          # lines written by main.py --out
  uv run src/validate_note.py --text "..." --tags factual_error
  add --check-urls to GET each link and require HTTP 200 (what the UrlValidity evaluator checks)

Exits 1 if any note fails. This does not reproduce X's ClaimOpinion or HarassmentAbuse scores.
"""
import argparse
import json
import re
import sys
import unicodedata

import requests

from data_models import MisleadingTag

URL_RE = re.compile(r"https?://\S+")
MAX_CHARS = 280
BANNED_PREFIXES = ("community note:", "note:")


def _has_emoji(text: str) -> bool:
    return any(unicodedata.category(ch) == "So" for ch in text)


def validate(note_text: str, tags: list[str], check_urls: bool = False) -> list[str]:
    """Return a list of problems; empty means the note passed."""
    problems: list[str] = []
    text = note_text.strip()
    urls = URL_RE.findall(text)
    if not text:
        problems.append("note is empty")
    if len(text) > MAX_CHARS:
        problems.append(f"{len(text)} chars, platform max is {MAX_CHARS}")
    without_urls = len(URL_RE.sub("", text).strip())
    if without_urls > MAX_CHARS:
        problems.append(f"{without_urls} chars without URLs, prompt max is {MAX_CHARS}")
    if not urls:
        problems.append("no source URL")
    if "#" in URL_RE.sub("", text):
        problems.append("contains a hashtag")
    if _has_emoji(text):
        problems.append("contains an emoji")
    if text.lower().startswith(BANNED_PREFIXES):
        problems.append("starts with a 'Community Note:'-style prefix")
    if "[source]" in text.lower():
        problems.append("contains '[Source]' filler")
    if not tags:
        problems.append("no misleading tags")
    valid = {t.value for t in MisleadingTag}
    bad = [t for t in tags if t not in valid]
    if bad:
        problems.append(f"unknown tags: {bad}")
    if check_urls:
        for url in urls:
            url = url.rstrip(").,;")
            try:
                code = requests.get(url, timeout=15, allow_redirects=True).status_code
            except requests.RequestException as e:
                code = type(e).__name__
            if code != 200:
                problems.append(f"URL not HTTP 200 ({code}): {url}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", help="JSON lines file of notes (post_id, note_text, misleading_tags)")
    parser.add_argument("--text", help="A single note's text")
    parser.add_argument("--tags", nargs="*", default=[], help="Misleading tags for --text")
    parser.add_argument("--check-urls", action="store_true", help="GET each URL and require HTTP 200")
    args = parser.parse_args()

    notes = []
    if args.file:
        with open(args.file) as f:
            notes = [json.loads(line) for line in f if line.strip()]
    elif args.text:
        notes = [{"post_id": "-", "note_text": args.text, "misleading_tags": args.tags}]
    else:
        parser.error("pass --file or --text")

    failed = 0
    for n in notes:
        problems = validate(n["note_text"], n.get("misleading_tags", []), args.check_urls)
        status = "FAIL" if problems else "PASS"
        print(f"[{status}] post {n['post_id']}: {n['note_text'][:80]}...")
        for p in problems:
            print(f"    - {p}")
        failed += bool(problems)
    print(f"\n{len(notes) - failed}/{len(notes)} notes passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
