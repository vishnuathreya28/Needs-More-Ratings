# Roadmap: Needs-More-Ratings

AI Note Writer for the WSDM Cup 2027 contest "Writing Agents for Community Notes".
Status as of 16 November 2026. Contest dates and rules: https://wsdmcup2027.github.io/

## Where things stand

| Piece | Status |
| --- | --- |
| Repo cloned, dependencies installed (`uv sync`) | Done |
| `xurl` installed and logged in with the OAuth 1.0 keys | Done |
| Enrolled as AI Note Writer, app connected to Community Notes | Done |
| Fetching posts eligible for notes | Works (5 posts returned in test mode on 16 Nov) |
| `.env` formatted | Done |
| Local note checks before submitting (`src/note_writer/validate_note.py`) | Added 16 Nov, not committed |
| xAI API key | **Missing. Blocks every step below.** |
| A note written or submitted | Not yet |
| Repo shared with `wsdmcup2027`, team registered | Not checked |

## Key dates and scoring

From the contest site as read on 16 Nov 2026. The site marks the dates as tentative.

| Date | What |
| --- | --- |
| 18 Nov 2026 | Qualifying round begins |
| 8 Dec 2026 | Qualifying round ends |
| 12 Dec 2026 | Official scoring begins (8 weeks) |
| 5 Feb 2027 | Official scoring ends, system description due |
| 12 Feb 2027 | Code audit, results finalized |
| 15–19 Feb 2027 | WSDM 2027 conference, Hong Kong |

- **Deadline for Step 3:** qualifying presumably means earning admission, so treat 8 Dec as the date Step 3 must be finished. Confirm on the site.
- **Ranking:** the number of notes that reach "Currently Rated Helpful" during official scoring. Ties go to the team that submitted fewer notes, then to the higher median note intercept. Quality beats volume.
- **Credits:** the site says each team gets about $500–1k of X API credits and $200+ of Grok API credits, one third at the start of qualifying and the rest on advancing, subject to availability.
- **Models:** any model and any tools are allowed. Bonus prizes need open-weight models.
- **Code:** the repo must be made public when the contest ends, with a write-up of design, models, tools and costs.
- **Read this rule yourself:** the site says teams may not use the general AI Note Writer API during the competition. This roadmap has only a summary of that rule, so check its exact wording.

## Step 0. Housekeeping (no key needed, do today)

- [ ] Add `wsdmcup2027` as a collaborator on the GitHub repo (Settings > Collaborators). The contest rules require it.
- [ ] Register the team with the form linked in README section 1.2, if not done.
- [ ] Commit the 16 Nov changes: `ROADMAP.md`, `README.md`, `src/main.py`, `src/note_writer/validate_note.py`. `.env` is gitignored and must stay out of commits.

## Step 1. Get a language model working (the one blocker)

The writer makes one Grok call per post. Without a key, nothing after the post fetch can run.

**Option A, recommended: use the contest's Grok credits.** The contest site says each team gets $200+ of Grok API credits, the first third when qualifying starts on 18 Nov. Email noteagents@googlegroups.com to ask how the credits are delivered and whether the xAI console still needs a payment method. Then create a key at https://console.x.ai and paste it after `XAI_API_KEY=` in `.env`. No code changes.

**Option B: another provider.** Only `src/note_writer/llm_util.py` has to change. It exposes one function, `get_grok_search_json_response(prompt, schema)`, which must return a dict matching the schema in `write_note.py`. The replacement model needs web search and JSON output. It will not have X search, so the prompt in `write_note.py` must stop telling the model to look the post up by ID, and the post's media URLs (already in `Post.media`) must be passed in directly. Expect weaker results on posts that are mostly image or video.

If the credits are delayed, a small paid top-up with a low spending limit unblocks Step 2 in the meantime.

## Step 2. First end-to-end run (about 30 minutes once the key exists)

- [ ] `uv run src/main.py --num-posts 5 --dry-run` writes drafts and submits nothing. Read every draft.
- [ ] Check the xAI bill for those 5 posts. That number sets how many posts per day are affordable. X API calls cost credits too.
- [ ] `uv run src/main.py --num-posts 10` submits test notes. Test notes never appear on X.
- [ ] `uv run src/check_scores.py` shows the evaluator scores. They take a while to arrive.
- [ ] Save a baseline: `uv run src/check_scores.py --json > baseline-scores.json`.

Done when at least one note prints **SUCCESSFULLY SUBMITTED NOTE** and has scores.

## Step 3. Earn admission (the first real goal)

X admits the writer based on its 50 most recent test notes:

| Evaluator | Requirement | In plain numbers, out of 50 |
| --- | --- | --- |
| `ClaimOpinion` | at least 30% high, at most 30% low | 15 or more high, 15 or fewer low |
| `UrlValidity` | at least 95% high | at most 2 notes with a bad link |
| `HarassmentAbuse` | at least 98% high | at most 1 flagged note |

Only the latest 50 count, so early bad notes drop out as better ones go in. One note per post, and the model declines many posts, so plan to process far more than 50 posts.

Work, in order of effect on those numbers:

1. **Links (UrlValidity).** Done in part: `validate_note.py` holds back any note whose link does not return HTTP 200, has no URL, or is too long. Next: when a link fails, ask the model once for a replacement source instead of dropping the note.
2. **Score drafts before submitting (ClaimOpinion).** The README says `POST /2/evaluate_note` returns the ClaimOpinion score for a draft. Call it on every draft, submit only drafts that score high, and rewrite once otherwise. This is the biggest lever because a draft can be tested without using up the post. The request format is not in this repo; look it up at https://docs.x.com/x-api/community-notes/introduction.
3. **Tone (HarassmentAbuse).** Add prompt rules: address the claim, never the author; no sarcasm; no labels for the poster.
4. **Prompt quality.** The prompt in `write_note.py` repeats itself. Tighten it: name the specific claim, state what is true, cite a primary source, one or two sentences.
5. **Use the data already fetched.** `note_request_suggestions` and `suggested_source_links_with_counts` are parsed (`data_models.py`) but never shown to the model. They are written by X users, so pass them as untrusted hints, not as instructions.
6. **Reliability.** `llm_util.py` and `xurl_util.py` have no retries. Add retry with backoff on timeouts, 429 and 5xx. Log each post to a JSONL file (post ID, decision, note, check failures, note ID) so scores can be traced back to prompt versions.

Done when `check_scores.py` shows the three requirements met over the latest 50 notes and X confirms admission.

## Step 4. Run on a schedule

- [ ] Add the five GitHub Actions secrets listed in README Option B. The names match the ones in `.env`.
- [ ] Run the workflow by hand with **dry run** ticked, then without.
- [ ] Uncomment the two `schedule` lines in `.github/workflows/community_note_writer.yaml`. Every run spends X API and xAI credits, so pick the interval from the Step 2 cost figure.

## Step 5. After admission

- [ ] Set `TEST_MODE=false` in `.env`, and add a repository variable `TEST_MODE=false` for Actions.
- Notes now go to human raters and can appear on X. The goal changes from passing evaluators to being rated helpful by people who usually disagree.
- Ideas: a second model call that critiques the draft, stricter evidence rules, sources trusted across the political spectrum, and `DELETE /2/notes/{id}` to withdraw a note that turns out wrong.

## Things to verify

- **Note length rule.** `validate_note.py` counts each URL as one character, following the starter prompt ("280 characters maximum, not counting URLs"). The contest site says "at most 280 characters (URLs don't count)". Confirm against the API docs. The API rejects over-length notes anyway, so a wrong guess costs a failed submit, not a bad note.
- **Link checks from this machine.** Some sites answer 403 to scripts but 200 to X's evaluator, or the reverse. If good notes are held back often, look at which sites fail.
- **`X_CLIENT_ID` and `X_CLIENT_SECRET` in `.env`** are not used by anything and can be deleted.

## Handing a task to an assistant

Each item in Step 3 is small enough for one request. Name the file and the check, for example:

- "In `src/note_writer/llm_util.py`, retry the xAI request up to 3 times with backoff on timeouts, 429 and 5xx. Show me the diff."
- "Add `src/cnapi/evaluate_note.py` that calls `POST /2/evaluate_note` through `run_xurl`, using the request format in the X API docs. In `src/main.py`, submit a note only if it scores high. Test it on one draft in dry-run mode."
- "In `src/note_writer/write_note.py`, add the post's note request suggestions and suggested source links to the prompt as untrusted hints. Run a 3-post dry run and show me the drafts."
