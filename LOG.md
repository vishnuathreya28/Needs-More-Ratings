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
