# Daily log

One entry per day, newest first. Record only what was actually done, with links to commits, PRs, or results.

Template:

```
## YYYY-MM-DD
- Done:
- Results / numbers:
- Blockers:
- Next:
```

## 2026-11-23
- Done: xAI key added to `.env`. First real runs: `main.py --num-posts 2 --dry-run`, then `--num-posts 10 --dry-run --concurrency 4`. Nothing submitted.
- Results / numbers: 10 posts -> 6 notes written, 3 NO NOTE NEEDED, 1 NOT ENOUGH EVIDENCE. `validate_note.py --check-urls`: 3/6 passed. Failures: 2 notes over 280 chars (352, 392), 3 links returned 403 (politico, apnews, stackexchange; likely bot-blocking of the checker, not dead links). One note (Biden video) is speculative ("appears unverified/old or altered").
- Done: Prompt fix in `src/note_writer/write_note.py`: 280-char limit now includes URLs, no hedging words (else NOT ENOUGH EVIDENCE), no opinions/advice, address the claim not the author, real publicly loading sources only. Drafts that fail `validate()` get one retry with the problems listed, and are not submitted if they still fail.
- Done: First real submission (test mode): `main.py --num-posts 10 --concurrency 4`. 4 notes submitted, 5 NO NOTE NEEDED, 1 NOT ENOUGH EVIDENCE. Log in `logs/submit-2026-11-23.log`.
- Results / numbers (evaluator scores, arrived within minutes): UrlValidity High 4/4, HarassmentAbuse High 4/4, ClaimOpinion High 2 / Medium 2 / Low 0. Medium: car defrosting (advice-like) and PS Store refunds (cited a guide site, not Sony). Already meets the admission ratios on this tiny sample; need 50 notes.
- Done: `main.py` now skips posts this writer already has a note on (from `GET /2/notes/search/notes_written`) before calling Grok. Tested live: 10 fetched, 4 skipped.
- Next: keep submitting batches of 10-20 per day to reach 50 notes before ~2026-12-08; push ClaimOpinion toward High (primary sources, skip advice/how-to posts).

## 2026-11-19
- Done: Added mock mode (`--mock`, `MOCK_GROK`, `MOCK_X_API`) and `src/validate_note.py` (offline checks: length, URL, hashtags, emoji, tags; optional `--check-urls`).
- Results / numbers: One end-to-end mock run: 4 posts fetched and parsed (incl. quoted, replied-to, media), 2 notes written, 1 NO NOTE NEEDED, 1 NOT ENOUGH EVIDENCE. 2/2 notes passed validation. Nothing published or submitted.
- Blockers: No real Grok call or X API fetch tested yet (no credits, no X credentials). URL checks could not run from the cloud sandbox.
- Done (local run): `main.py --mock --out notes.jsonl` on Vishnu's machine, then `validate_note.py --check-urls`. Run outputs (notes*.jsonl, logs) now gitignored.
- Results / numbers (local run): 2 notes written, 1/2 passed with URL checks. The NASA link in the Great Wall mock reply returns 404; the Scientific American link returns 200. The 404 is in the canned mock fixture, not in a real Grok output.
- Next: When credits land, run `--dry-run` with real keys, then `validate_note.py --check-urls`.

## 2026-11-18
- Done: WSDM Cup 2027 registration confirmed (email from organizers).
- Done: Received $500 X API voucher (redeem at console.x.com > Credits > Redeem Voucher by ~2026-12-18; credits expire 90 days after redeeming).
- Blockers: Grok credits delayed by an internal error on the provider side. $67 pending now, $133 due at the official scoring round.
- Next: Get the writer through the automated admission suite (qualifying closes ~2026-12-08).
