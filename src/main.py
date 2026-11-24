import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List

import dotenv

import refusal_cache
from check_scores import get_all_test_notes_written
from cnapi.get_api_eligible_posts import get_posts_eligible_for_notes
from cnapi.submit_note import submit_note
from data_models import NoteResult, PostWithContext
from note_writer.llm_util import USAGE
from note_writer.write_note import research_post_and_write_note


def _xurl_error_details(exc: Exception) -> str:
    """xurl prints the X API's error response to stdout; surface it instead of a bare exit code."""
    if isinstance(exc, subprocess.CalledProcessError):
        return ((exc.stdout or "") + (exc.stderr or "")).strip() or str(exc)
    return str(exc)


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() == "true"


def _check_setup() -> None:
    """Fail early, with a clear message, on the most common setup problems."""
    if not _env_true("MOCK_GROK") and not os.getenv("XAI_API_KEY"):
        sys.exit("XAI_API_KEY is not set. Copy .env.example to .env and fill in your xAI API key.")
    if not _env_true("MOCK_X_API") and shutil.which("xurl") is None:
        sys.exit("xurl is not installed, or its folder is not on your PATH. See step A.1 of the README.")


def _worker(
    post_with_context: PostWithContext,
    dry_run: bool = False,
    test_mode: bool = True,
    out_path: str | None = None,
    refusals: dict | None = None,
):
    """
    Fetch and try to write and submit a note for one post.
    If `dry_run` is True, do not submit notes to the API, just print them to the console.
    """
    note_result: NoteResult = research_post_and_write_note(post_with_context)

    log_strings: List[str] = ["-" * 20, f"Post: {post_with_context.post.post_id}", "-" * 20]
    if note_result.context_description is not None:
        log_strings.append(
            f"\n*POST TEXT AND ANY QUOTED OR REPLIED-TO POST:*\n{note_result.context_description}\n"
        )
    if note_result.error is not None:
        log_strings.append(f"\n*{'BLOCKED' if note_result.blocked else 'ERROR'}:* {note_result.error}")
        if note_result.blocked and refusals is not None:
            refusal_cache.record(refusals, post_with_context.post.post_id, refusal_cache.BLOCKED)
    if note_result.refusal:
        log_strings.append(f"\n*REFUSAL:* {note_result.refusal}")
        if refusals is not None:
            refusal_cache.record(refusals, post_with_context.post.post_id, note_result.refusal)
    if note_result.note:
        log_strings.append(f"\n*NOTE:*\n  {note_result.note.note_text}\n")
        log_strings.append(
            f"\n*MISLEADING TAGS:*\n  {[tag.value for tag in note_result.note.misleading_tags]}\n"
        )
        if note_result.claim_opinion_score is not None:
            log_strings.append(f"\n*CLAIMOPINION SCORE:* {note_result.claim_opinion_score:.2f}\n")

    if note_result.note is not None and out_path:
        with open(out_path, "a") as f:
            row = note_result.note.model_dump(mode="json")
            row["claim_opinion_score"] = note_result.claim_opinion_score
            f.write(json.dumps(row) + "\n")

    if note_result.note is not None and not dry_run:
        try:
            response = submit_note(
                note=note_result.note,
                test_mode=test_mode,
                verbose_if_failed=False,
            )
            note_id = response["data"]["id"]
            log_strings.append(f"\n*SUCCESSFULLY SUBMITTED NOTE*\nNote ID: {note_id}\n")
        except Exception as e:
            log_strings.append(
                "\n*ERROR SUBMITTING NOTE* (if it says a note already exists, we already wrote a note "
                f"on this post; moving on):\n{_xurl_error_details(e)}\n"
            )
    print("".join(log_strings) + "\n")


def _skip_already_noted(posts: List[PostWithContext], test_mode: bool) -> List[PostWithContext]:
    """
    Drop posts this writer already has a note on, before spending a Grok call on them.
    A writer can submit only one note per post, so a second draft would be rejected anyway.
    """
    if _env_true("MOCK_X_API"):
        return posts
    try:
        written = get_all_test_notes_written(test_mode=test_mode)
    except Exception as e:
        print(f"Could not list notes already written, processing all posts anyway:\n{_xurl_error_details(e)}\n")
        return posts
    noted = {str((n.get("info") or {}).get("post_id")) for n in written}
    kept = [p for p in posts if str(p.post.post_id) not in noted]
    skipped = len(posts) - len(kept)
    if skipped:
        print(f"Skipping {skipped} posts that already have a note from this writer")
    return kept


def main(
    num_posts: int = 10,
    dry_run: bool = False,
    concurrency: int = 1,
    test_mode: bool = True,
    out_path: str | None = None,
    recheck_refusals: bool = False,
):
    """
    Get up to `num_posts` recent posts eligible for notes and write notes for them.
    If `dry_run` is True, do not submit notes to the API, just print them to the console.
    """

    print(f"Getting up to {num_posts} recent posts eligible for notes (test_mode={test_mode})")
    try:
        eligible_posts: List[PostWithContext] = get_posts_eligible_for_notes(
            max_results=num_posts, test_mode=test_mode
        )
    except subprocess.CalledProcessError as e:
        sys.exit(
            "Could not fetch posts eligible for notes. The X API said:\n"
            f"{_xurl_error_details(e)}\n\n"
            "Check that xurl is logged in (`xurl auth status`, README step A.1), that your account is "
            "enrolled as an AI Note Writer (README step 2.2), and that your app has Read and write "
            "permissions (README step 2.1)."
        )
    print(f"Found {len(eligible_posts)} recent posts eligible for notes")
    print(
        f"  Eligible Post IDs: {', '.join([str(post_with_context.post.post_id) for post_with_context in eligible_posts])}\n"
    )
    eligible_posts = _skip_already_noted(eligible_posts, test_mode)
    # Mock runs never touch the real refusal file
    refusals = None if _env_true("MOCK_GROK") else refusal_cache.load()
    if refusals and not recheck_refusals:
        before = len(eligible_posts)
        eligible_posts = [p for p in eligible_posts if str(p.post.post_id) not in refusals]
        if before - len(eligible_posts):
            print(
                f"Skipping {before - len(eligible_posts)} posts recently declined or blocked "
                "(see refusals.json; --recheck-refusals to override)"
            )
    if len(eligible_posts) == 0:
        print("No posts to process.")
        return

    try:
        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [
                    executor.submit(_worker, post, dry_run, test_mode, out_path, refusals)
                    for post in eligible_posts
                ]
                for future in futures:
                    future.result()
        else:
            for post in eligible_posts:
                _worker(post, dry_run, test_mode, out_path, refusals)
    finally:
        if refusals is not None:
            refusal_cache.save(refusals)
        _print_usage(len(eligible_posts))
    print("Done.")


def _print_usage(num_posts: int) -> None:
    if not USAGE["calls"]:
        return
    line = (
        f"Grok usage: {USAGE['calls']} calls for {num_posts} posts, "
        f"{USAGE['input_tokens']:,} input / {USAGE['output_tokens']:,} output tokens"
    )
    if USAGE["cost_known"]:
        line += f", cost ${USAGE['cost_usd']:.4f} (${USAGE['cost_usd'] / max(num_posts, 1):.4f} per post)"
    else:
        line += ", cost not reported by the API (check console.x.ai)"
    print(line)


if __name__ == "__main__":
    dotenv.load_dotenv()
    parser = argparse.ArgumentParser(description="Run note‑writing bot once.")
    parser.add_argument(
        "--num-posts", type=int, default=10, help="Number of posts to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not submit notes to the API, just print them to the console",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent tasks to run",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use canned Grok answers and canned posts (same as MOCK_GROK=true MOCK_X_API=true). Forces --dry-run.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Append each written note as a JSON line to this file (check it with src/validate_note.py)",
    )
    parser.add_argument(
        "--recheck-refusals",
        action="store_true",
        help="Research posts again even if Grok declined them recently (ignores refusals.json)",
    )
    args = parser.parse_args()
    if args.mock:
        os.environ["MOCK_GROK"] = "true"
        os.environ["MOCK_X_API"] = "true"
    if _env_true("MOCK_GROK") or _env_true("MOCK_X_API"):
        if not args.dry_run:
            print("Mock mode is on: forcing --dry-run, nothing will be submitted.")
        args.dry_run = True
    _check_setup()
    main(
        num_posts=args.num_posts,
        dry_run=args.dry_run,
        concurrency=args.concurrency,
        test_mode=os.getenv("TEST_MODE", "true").strip().lower() != "false",
        out_path=args.out,
        recheck_refusals=args.recheck_refusals,
    )
