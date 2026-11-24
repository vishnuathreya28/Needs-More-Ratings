from cnapi.evaluate_note import claim_opinion_score
from data_models import (
    MisleadingTag,
    NoteResult,
    PostWithContext,
    ProposedMisleadingNote,
)
from note_writer.llm_util import get_grok_search_json_response
from validate_note import validate

NO_NOTE_NEEDED = "NO NOTE NEEDED"

# Raw POST /2/evaluate_note scores vs the ClaimOpinion buckets of our first 13 notes (2026-11-23):
# High were all > 0.17, Medium -1.68 to -0.12, Low < -2.3.
HIGH_SCORE = 0.0  # below this, ask Grok for one rewrite
MIN_SCORE = -1.0  # below this, do not submit: keeps out Lows and the weaker Mediums that dilute the High share
NOT_ENOUGH_EVIDENCE = "NOT ENOUGH EVIDENCE"

NOTE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["WRITE NOTE", NO_NOTE_NEEDED, NOT_ENOUGH_EVIDENCE]},
        "note_text": {"type": "string"},
        "misleading_tags": {
            "type": "array",
            "items": {"type": "string", "enum": [tag.value for tag in MisleadingTag]},
        },
    },
    "required": ["decision", "note_text", "misleading_tags"],
    "additionalProperties": False,
}


def _get_prompt_for_note_writing(post_with_context_description: str):
    return f"""Below will be a post on X. Do research on the post using web search and X search to determine if \
the post is potentially misleading. Use X search to look up the post by its Post ID, \
including any images or video in it, and any quoted or replied-to post by its Post ID. \
If the post is misleading and needs a community note, \
then your decision should be "WRITE NOTE" and note_text should be the proposed community note itself. \
If the post is not misleading, or does not contain any concrete fact-checkable claims, or there \
is not strong enough evidence to write a well-supported \
community note, then do not write a note, and instead set decision to "{NO_NOTE_NEEDED}" or \
"{NOT_ENOUGH_EVIDENCE}".

If a note is justified, then please write \
a very good community note, which is concise, interesting and clear to read, \
contains no unnecessary words, is backed by very solid evidence from sources that would be most likely \
to be found trustworthy by people on both sides of the political spectrum (citing URL(s)), and is \
written in a way that would be most likely to be found trustworthy by people on both sides of the \
political spectrum. \

HARD LENGTH LIMIT: the ENTIRE note, INCLUDING every URL, must be 280 characters or fewer. \
Count the URL characters too. Aim for one or two sentences of about 150-200 characters plus ONE URL. \
Use a second URL only if it still fits within 280 characters total. \
The note should not include any sort of wasted characters e.g. [Source] when listing a URL. Just state the URL directly in the text. \
Each note MUST include at least one URL/link source. Nothing else counts as a source other than a URL/link. \
Each note MUST NOT use any hashtags (#). Keep a professional tone with no hashtags, emojis, etc. \

Sources: every URL must be a real page you actually found in your search that loads publicly \
(no paywall, no login). Prefer primary sources (official sites, government or company statements, \
original documents, the original publisher of a quote or video) and widely trusted references. \
Never invent or guess a URL. \

How to write the note (this matters most):
- The first sentence must name the post's specific claim and directly say what is wrong with it, \
e.g. "Iran has not attacked the US mainland." or "The transcript is fabricated; the Premier League \
says no such audio exists." or "The photo is from a 2019 protest in Chile, not this event."
- The second sentence (optional) gives the key correcting fact: the real number, date, quote, or origin, with the source.
- Never write a note that only states a related fact without saying how it contradicts the post. \
Bad: "GTA VI released November 19, 2026." Good: "GTA VI is already out; it released November 19, 2026, \
not in 2027 as the post says."
- Avoid weak framings like "No credible reports confirm..." when you can state what is actually true instead.
- Do NOT hedge or speculate. Never use words like "appears", "seems", "likely", "possibly", "may be", \
"reportedly", or "unverified". If you can only hedge, the decision is "{NOT_ENOUGH_EVIDENCE}".
- Do NOT state opinions, predictions, advice, how-to tips, or value judgements. Posts that are mainly \
advice, jokes, personal experiences, or predictions get "{NO_NOTE_NEEDED}".
- Address the claim, never the author: no sarcasm, no characterising the poster's motives or intelligence, \
no labels for the poster.
- Do not add background facts that do not directly correct the post's claim.

If the post does not need a community note (either because the original post is not misleading, \
or does not contain any concrete fact-checkable claims, \
then your decision should simply be "{NO_NOTE_NEEDED}".

If the post may need a community note, but you weren't able to find enough concrete evidence to \
write an ironclad community note, then your decision should be \
"{NOT_ENOUGH_EVIDENCE}".

If you are writing a note, don't preface it with anything like "Community Note:". Just write the note.

If you are writing a note, also identify which of the following misleading_tags apply to the post and note. \
You may choose as many tags as apply, but you must choose at least one:
- "factual_error":  # the post contains a factual error
- "manipulated_media":  # the post contains manipulated/fake/out-of-context media
- "outdated_information":  # the post contains outdated information
- "missing_important_context":  # the post is missing important context
- "disputed_claim_as_fact":  # including unverified claims
- "misinterpreted_satire":  # the post is satire that may likely be misinterpreted as fact
- "other":  # the post contains other misleading reasons

If you are not writing a note, set note_text to an empty string and misleading_tags to an empty list.

Post:

    {post_with_context_description}
    """


def _get_post_with_context_description_for_prompt(post_with_context: PostWithContext) -> str:
    description = f"""Post ID: {post_with_context.post.post_id}
Post text:
```
{post_with_context.post.text}
```
"""
    if post_with_context.quoted_post:
        description += f"""The post of interest had quoted (referenced) another post (Post ID: {post_with_context.quoted_post.post_id}). Here is the quoted post's text:
```
{post_with_context.quoted_post.text}
```
"""

    if post_with_context.in_reply_to_post:
        description += f"""The post of interest was a reply to another post (Post ID: {post_with_context.in_reply_to_post.post_id}). Here is the replied-to post's text:
```
{post_with_context.in_reply_to_post.text}
```
"""

    return description


def research_post_and_write_note(
    post_with_context: PostWithContext,
) -> NoteResult:
    post_with_context_description = _get_post_with_context_description_for_prompt(post_with_context)

    try:
        note_prompt = _get_prompt_for_note_writing(post_with_context_description)
        response = get_grok_search_json_response(note_prompt, NOTE_RESPONSE_SCHEMA)
        problems = _draft_problems(response)
        if problems:
            # One retry: show Grok its draft and what is wrong with it.
            retry_prompt = (
                note_prompt
                + "\n\nYour previous draft note was:\n"
                + response["note_text"]
                + "\n\nIt broke these rules: "
                + "; ".join(problems)
                + ". Write a corrected answer that follows every rule, or choose "
                + f'"{NOT_ENOUGH_EVIDENCE}" if a rule-following note is not possible.'
            )
            response = get_grok_search_json_response(retry_prompt, NOTE_RESPONSE_SCHEMA)
            problems = _draft_problems(response)
    except Exception as e:
        return NoteResult(post=post_with_context, error=str(e), context_description=post_with_context_description)

    if response["decision"] != "WRITE NOTE":
        return NoteResult(post=post_with_context, refusal=response["decision"], context_description=post_with_context_description)

    score = None
    if not problems:
        try:
            score = claim_opinion_score(post_with_context.post.post_id, response["note_text"])
            if score is not None and score < HIGH_SCORE:
                # One rewrite aimed at the ClaimOpinion evaluator; keep whichever draft scores higher.
                rewrite_prompt = (
                    note_prompt
                    + "\n\nYour previous draft note was:\n"
                    + response["note_text"]
                    + "\n\nX's evaluator judged that it does not clearly address the post's claim, or reads "
                    "as opinion. Rewrite it so the first sentence names the post's specific claim and says "
                    "directly what is wrong with it, then the correcting fact and source. Same rules as above. "
                    f'Choose "{NOT_ENOUGH_EVIDENCE}" if you cannot.'
                )
                retry = get_grok_search_json_response(rewrite_prompt, NOTE_RESPONSE_SCHEMA)
                if retry["decision"] == "WRITE NOTE" and not _draft_problems(retry):
                    retry_score = claim_opinion_score(post_with_context.post.post_id, retry["note_text"])
                    if retry_score is not None and retry_score > score:
                        response, score = retry, retry_score
        except Exception as e:
            return NoteResult(post=post_with_context, error=str(e), context_description=post_with_context_description)
        if score is not None and score < MIN_SCORE:
            return NoteResult(
                post=post_with_context,
                blocked=True,
                error=f"ClaimOpinion score {score:.2f} is below the {MIN_SCORE} cutoff, not submitting. Draft: {response['note_text']}",
                context_description=post_with_context_description,
            )

    if problems:
        return NoteResult(
            post=post_with_context,
            blocked=True,
            error=f"Draft still failed checks after one retry, not submitting: {problems}. Draft: {response['note_text']}",
            context_description=post_with_context_description,
        )

    return NoteResult(
        post=post_with_context,
        note=ProposedMisleadingNote(
            post_id=post_with_context.post.post_id,
            note_text=response["note_text"],
            misleading_tags=[MisleadingTag(tag) for tag in response["misleading_tags"]],
        ),
        claim_opinion_score=score,
        context_description=post_with_context_description,
    )


def _draft_problems(response: dict) -> list[str]:
    """Offline checks (length, URL present, no hashtags, tags) for a WRITE NOTE answer; [] otherwise."""
    if response["decision"] != "WRITE NOTE":
        return []
    return validate(response["note_text"], response["misleading_tags"])
