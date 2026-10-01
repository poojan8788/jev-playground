"""
Shared setup for LOT-CRAWLER: constants, domain context/dataset loading,
logging, token/client helpers, and the Jev/Claude call wrappers + prompts.
Imported by both pages/1_Compliance_Checker.py and pages/2_Scaling_This_Tool.py
(and by app.py, the multipage entry point). No Streamlit page-rendering code
lives here — only setup and helper functions, so it's safe to import before
st.set_page_config runs in app.py.
"""

import os
import json
import time
import logging
import datetime

import streamlit as st
import requests
import anthropic
import httpx
from dotenv import load_dotenv

from action_codes import format_code_glossary  # noqa: F401  (re-exported for pages)

load_dotenv()  # loads variables from .env in this directory, if present

APP_NAME = "LOT-CRAWLER"
APP_TAGLINE = "initial prototype"

DOMAIN_CONTEXT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "domain_context.md"
)


def load_domain_context():
    """Static Copart lot/seller domain glossary (see domain_context.md),
    researched from the g2-ssm and g2-seller repos. Fed to both Jev and
    Claude on every run so they judge compliance with the same background
    understanding of lot stages, title handling, release issues, and note
    action codes — instead of just the raw seller instructions + lot notes.
    """
    try:
        with open(DOMAIN_CONTEXT_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


DOMAIN_CONTEXT = load_domain_context()

LOTS_DATASET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "lots_dataset.json"
)


def load_lots_dataset():
    """Real lot instructions/notes pairs, pre-built by build_dataset.py from
    Instructions(Sheet1).csv + jevnotes(Sheet1/Sheet2).csv. Returns {} if the
    dataset hasn't been built yet, so the picker UI just doesn't show."""
    try:
        with open(LOTS_DATASET_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


LOTS_DATASET = load_lots_dataset()

DATASET_STATS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "dataset_stats.json"
)


def load_dataset_stats():
    """Static counts (lots per seller, stage/status breakdowns, raw source
    row counts) pre-computed by build_dataset.py, so the Dataset Stats page
    doesn't need the source CSVs (~/Downloads) present at runtime. Returns
    {} if the stats file hasn't been built yet."""
    try:
        with open(DATASET_STATS_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


DATASET_STATS = load_dataset_stats()

JEV_VS_CLAUDE_RESULTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "jev_vs_claude_results.json"
)


def load_jev_vs_claude_results():
    """Static Jev-vs-Claude compliance-check results for a fixed sample of 7
    real lots (built by build_jev_vs_claude_results.py + reclassify_jev_vs_claude.py),
    used by the 'Jev vs Claude Results' page. Returns {"lots": []} if the
    file hasn't been built yet."""
    try:
        with open(JEV_VS_CLAUDE_RESULTS_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"lots": []}


JEV_VS_CLAUDE_RESULTS = load_jev_vs_claude_results()

# Rough per-token pricing used only to *estimate* Claude cost for the
# usage/cost comparison — the Genie gateway response doesn't include a
# billed cost the way Jev's response does. Override via env vars if you
# know the actual contracted rate.
CLAUDE_PRICE_PER_MTOK_INPUT = float(os.environ.get("CLAUDE_PRICE_INPUT_PER_MTOK", "3.0"))
CLAUDE_PRICE_PER_MTOK_OUTPUT = float(os.environ.get("CLAUDE_PRICE_OUTPUT_PER_MTOK", "15.0"))


def estimate_claude_cost(input_tokens, output_tokens):
    return (input_tokens / 1_000_000) * CLAUDE_PRICE_PER_MTOK_INPUT + (
        output_tokens / 1_000_000
    ) * CLAUDE_PRICE_PER_MTOK_OUTPUT

COPART_ROUTER_ROOT = "http://ai.copart.com/router"
COPART_ROUTER_BASE = f"{COPART_ROUTER_ROOT}/v1"  # used for Jev's REST endpoint
JEV_ENDPOINT = f"{COPART_ROUTER_BASE}/systemone"
JEV_MODEL = "openrouter/jev-latest"
CLAUDE_MODEL = "anthropic/claude-sonnet-5"

# Two known gateways for Claude: the ops-portal JWT router (has been 403ing for
# Claude models on this account) and Copart's Genie gateway (what Claude Code
# CLI itself uses, with a separate sk-... API key that IS entitled for Claude).
# Selectable via env var so no gateway/key choice is hardcoded.
CLAUDE_GATEWAY = os.environ.get("CLAUDE_GATEWAY", "genie").strip().lower()
GATEWAYS = {
    "router": {
        "base_url": COPART_ROUTER_ROOT,  # anthropic SDK appends /v1/messages itself
        "token_env": "COPART_AI_TOKEN",
    },
    "genie": {
        "base_url": "https://genie.copart.com/api",
        "token_env": "GENIE_AI_TOKEN",
    },
}

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(
    LOG_DIR, f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logger = logging.getLogger("jev_compliance")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(file_handler)

logger.info("=== Streamlit app started, logging to %s ===", LOG_FILE)
logger.info(
    "Domain context loaded: %s chars from %s",
    len(DOMAIN_CONTEXT),
    DOMAIN_CONTEXT_PATH,
)


def redact(text, token):
    if not token:
        return text
    return text.replace(token, "***REDACTED***")


def _redacted_headers(headers):
    h = dict(headers)
    for key in list(h.keys()):
        if key.lower() in ("authorization", "x-api-key"):
            h[key] = "***REDACTED***"
    return h


def log_httpx_request(request):
    body = request.content.decode("utf-8", errors="replace") if request.content else ""
    logger.debug(
        "HTTPX REQUEST %s %s\nheaders=%s\nbody=%s",
        request.method,
        request.url,
        _redacted_headers(request.headers),
        body,
    )


def log_httpx_response(response):
    response.read()
    logger.debug(
        "HTTPX RESPONSE status=%s url=%s\nheaders=%s\nbody=%s",
        response.status_code,
        response.request.url,
        dict(response.headers),
        response.text,
    )


def get_token():
    """Token for Jev, always via the ops-portal router."""
    sidebar_token = st.session_state.get("token_override", "").strip()
    if sidebar_token:
        return sidebar_token
    return os.environ.get("COPART_AI_TOKEN", "").strip()


def get_claude_token():
    """Token for Claude, gateway-dependent (router JWT vs Genie sk- key)."""
    sidebar_token = st.session_state.get("claude_token_override", "").strip()
    if sidebar_token:
        return sidebar_token
    token_env = GATEWAYS[CLAUDE_GATEWAY]["token_env"]
    return os.environ.get(token_env, "").strip()


def make_anthropic_client(token):
    base_url = GATEWAYS[CLAUDE_GATEWAY]["base_url"]
    http_client = httpx.Client(
        event_hooks={"request": [log_httpx_request], "response": [log_httpx_response]}
    )
    return anthropic.Anthropic(
        base_url=base_url, auth_token=token, http_client=http_client
    )


def call_claude(client, system, user, max_tokens=8192):
    logger.info(
        "Calling Claude model=%s gateway=%s base_url=%s",
        CLAUDE_MODEL,
        CLAUDE_GATEWAY,
        GATEWAYS[CLAUDE_GATEWAY]["base_url"],
    )
    start = time.perf_counter()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    elapsed = time.perf_counter() - start
    if message.stop_reason == "max_tokens":
        logger.warning("Claude response truncated by max_tokens=%s", max_tokens)
    text_blocks = [block.text for block in message.content if block.type == "text"]
    text = "\n".join(text_blocks)
    usage = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "thinking_tokens": getattr(
            message.usage.output_tokens_details, "thinking_tokens", 0
        )
        if getattr(message.usage, "output_tokens_details", None)
        else 0,
        "elapsed_sec": elapsed,
    }
    usage["estimated_cost"] = estimate_claude_cost(
        usage["input_tokens"], usage["output_tokens"]
    )
    return text, usage


def call_jev(token, state_text, questions):
    payload = {"model": JEV_MODEL, "state": state_text, "questions": questions}
    logger.info("Calling Jev url=%s", JEV_ENDPOINT)
    logger.debug("Jev request body=%s", json.dumps(payload))
    start = time.perf_counter()
    resp = requests.post(
        JEV_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    elapsed = time.perf_counter() - start
    logger.debug(
        "Jev response status=%s headers=%s body=%s",
        resp.status_code,
        dict(resp.headers),
        resp.text,
    )
    resp.raise_for_status()
    result = resp.json()
    raw_usage = result.get("usage", {})
    usage = {
        "input_tokens": raw_usage.get("input_tokens", 0),
        "output_tokens": raw_usage.get("output_tokens", 0),
        "cost": raw_usage.get("cost", 0),
        "elapsed_sec": elapsed,
    }
    return result, usage


# Jev questions targeting the "good fit" checks discussed: semantic/categorical
# compliance judgments, not date/dollar arithmetic (that would need pre-parsing).
#
# Fairness note: every question below repeats the same stage-applicability
# rule given to Claude in CLAUDE_JUDGE_SYSTEM ("an instruction that hasn't
# been reached yet is not-yet-applicable, not a violation") directly in its
# own instructions text. This was added after an early Jev-vs-Claude run
# showed Jev's overall_compliance_severity score landing in the uncertain
# middle of its scale on lots Claude confidently called "no deviation" —
# almost always early-stage lots where most instructions simply hadn't come
# up yet. Jev answers each question independently in one pass (no visibility
# into its other answers), so it can't be told to "roll up" the other 5
# dimensions the way Claude does implicitly — instead, overall_severity spells
# out the same not-yet-applicable rule and the same "no deviation covers nothing
# applicable yet" framing that Claude already uses, so both engines are scoring
# against the same rubric rather than Jev being asked a vaguer question.
JEV_QUESTIONS = {
    "escalation_followed": {
        "type": "noul",
        "instructions": (
            "Do the lot notes show that any release issue, high charge, or "
            "advance charge requiring escalation was actually escalated the way "
            "the seller instructions require (e.g. emailed to the seller support "
            "address, or approved by a supervisor/GM)? If nothing in the notes "
            "yet requires escalation at this lot's current stage, that counts as "
            "compliant (true) — not-yet-applicable is not a violation."
        ),
    },
    "title_handling": {
        "type": "choice",
        "instructions": (
            "Based on the lot notes, how is the title being handled relative to "
            "the seller's title instructions? If the lot hasn't reached the "
            "stage where title instructions apply yet, that is not_applicable, "
            "not inconsistent."
        ),
        "criteria": {
            "consistent": "Title handling in the notes matches the seller's title instructions",
            "inconsistent": "Title handling in the notes conflicts with the seller's title instructions",
            "not_applicable": "Notes don't yet show title-related activity to judge, or the lot hasn't reached the stage where title instructions apply",
        },
    },
    "communication_compliance": {
        "type": "choice",
        "instructions": (
            "Which best describes how communication/contact with the seller or "
            "owner was handled in the notes, relative to the seller's "
            "instructions? If no communication has been required yet at this "
            "lot's current stage, that counts as compliant, not partial or "
            "noncompliant."
        ),
        "criteria": {
            "compliant": "Communications followed the seller's stated contacts/process, or no communication was required yet at this stage",
            "partial": "Some communication happened but missed a required step or contact",
            "noncompliant": "Required communication per seller instructions is missing",
        },
    },
    "billing_compliance": {
        "type": "choice",
        "instructions": (
            "Which best describes how charges/billing (advance charges, "
            "dollar-threshold approvals, itemized breakdowns) were handled in "
            "the notes, relative to the seller's billing instructions? If the "
            "lot hasn't reached the stage where billing instructions apply yet, "
            "that is not_applicable, not partial or noncompliant."
        ),
        "criteria": {
            "compliant": "Charges were approved/documented the way the seller's billing instructions require",
            "partial": "Some charge handling happened but missed a required approval or breakdown",
            "noncompliant": "Required charge approval/breakdown per seller instructions is missing",
            "not_applicable": "Notes don't yet show any billing/charge activity to judge, or the lot hasn't reached the stage where billing instructions apply",
        },
    },
    "pickup_dispatch_compliance": {
        "type": "choice",
        "instructions": (
            "Which best describes how pickup/dispatch (contacting the pickup "
            "location, getting quotes for non-standard tows, using allowed "
            "contact methods) was handled in the notes, relative to the "
            "seller's dispatch instructions? If the lot hasn't reached the "
            "stage where dispatch instructions apply yet, that is "
            "not_applicable, not partial or noncompliant."
        ),
        "criteria": {
            "compliant": "Pickup/dispatch followed the seller's stated process (quotes, contacts, approvals)",
            "partial": "Some pickup/dispatch steps happened but missed a required step",
            "noncompliant": "Required pickup/dispatch step per seller instructions is missing",
            "not_applicable": "Notes don't yet show pickup/dispatch activity to judge, or the lot hasn't reached the stage where dispatch instructions apply",
        },
    },
    "overall_compliance_severity": {
        "type": "score",
        "instructions": (
            "Overall, how severe is any ACTUAL deviation from the seller's "
            "standing instructions found in these lot notes, counting ONLY "
            "instructions that are already applicable at this lot's current "
            "stage? Instructions tied to a later stage the lot hasn't reached "
            "yet (e.g. title transmittal before title-stage, billing approval "
            "before any charges exist) do not count toward severity at all — "
            "score those as no deviation, the same way you would if every "
            "currently-applicable instruction were followed. Only score minor "
            "or major when an instruction that is ALREADY applicable right now "
            "was actually not followed."
        ),
        "criteria": [
            "No deviation - fully compliant with every currently-applicable instruction (includes lots where most instructions aren't applicable yet)",
            "Minor deviation - a currently-applicable instruction was followed loosely, or has a small documentation/verifiability gap, but no real risk",
            "Major deviation - a currently-applicable instruction was clearly not followed, needs review",
        ],
    },
}

CLAUDE_JUDGE_SYSTEM = f"""You are a compliance reviewer for Copart lot operations.
You will be given a seller code's standing instructions (assignment, billing,
dispatch, title notes) and the free-text note history for one lot at that
seller code. Judge whether the lot's handling, as shown in the notes, complied
with the seller's standing instructions.

Use the domain background below to interpret lot stages, title handling,
release issues, and note action codes correctly — in particular, judge an
instruction as "not yet applicable" rather than a violation if the lot
hasn't reached the stage where that instruction becomes relevant.

The pasted seller instructions and lot notes are free text copied from a
spreadsheet, and may be missing column headers or have some columns
omitted entirely (see "Handling Incomplete or Missing Column Structure" in
the domain background). Do not treat missing structure/metadata as a
violation — judge from whatever content is present, and say explicitly
when missing data (e.g. no timestamps) limits what you can verify.

--- DOMAIN BACKGROUND ---
{DOMAIN_CONTEXT}
--- END DOMAIN BACKGROUND ---

Respond with a short structured verdict covering:
1. escalation_followed (yes/no/unclear + why)
2. title_handling (consistent/inconsistent/not_applicable + why)
3. communication_compliance (compliant/partial/noncompliant + why)
4. billing_compliance (compliant/partial/noncompliant/not_applicable + why)
5. pickup_dispatch_compliance (compliant/partial/noncompliant/not_applicable + why)
6. overall_compliance_severity (no deviation / minor / major + why)

For overall_compliance_severity specifically: count ONLY instructions that
are already applicable at this lot's current stage. Instructions tied to a
later stage the lot hasn't reached yet do not count toward severity at
all — score those as "no deviation," the same as if every currently-
applicable instruction were followed. Only call it minor or major when an
instruction that is ALREADY applicable right now was actually not followed.

Be concise. Cite specific note lines/timestamps where relevant. If the
instructions require something that can't be verified from the notes alone
(e.g. exact elapsed days, dollar thresholds), say so explicitly rather than
guessing."""

STAGE_SUMMARY_SYSTEM = """You summarize Copart lot note histories. Given raw,
often terse/abbreviated lot notes, produce a short plain-English summary of:
- what stage the lot is currently in
- what has happened so far (key events in order)
- what is currently blocking or pending, if anything
Keep it under 150 words. Do not judge compliance here, just summarize."""

JEV_EXPLAIN_SYSTEM = f"""You explain the output of TypeSafe's Jev model to a
non-technical reader. Jev is a non-autoregressive "System-1" model that
answers structured questions with calibrated typed decisions instead of free
text. There are three answer types:

- noul: a single probability (0-1) that a yes/no proposition is true. There
  is no separate confidence score — the probability itself IS the
  confidence (0.5 = maximally uncertain, close to 0 or 1 = confident).
- choice: picks one named option from a fixed set, and reports a
  probability for every option plus an overall confidence score.
- score: picks a point on an ordered/graded scale (e.g. no deviation /
  minor / major), with a legend describing each level, probabilities per
  level, and a confidence score.

You will be given: (1) the raw JSON answers Jev produced for a lot
compliance check, and (2) the seller instructions and lot notes that were
actually fed to Jev to produce those answers. The six questions Jev
answers, and what each one means in plain terms, are:

- escalation_followed [noul]: did the lot notes show that a release issue,
  high charge, or advance charge needing escalation (e.g. emailed to
  seller support, or approved by a supervisor/GM) was actually escalated
  the way the seller's instructions require?
- title_handling [choice: consistent / inconsistent / not_applicable]:
  does how the title was handled in the notes match the seller's title
  instructions (e.g. Title Direct vs Title Standard, salvage vs clean)?
  "not_applicable" means the lot hasn't reached a stage where title
  activity would show up yet.
- communication_compliance [choice: compliant / partial / noncompliant]:
  did contact with the seller/owner follow the seller's required process
  (who to contact, what's allowed, e.g. "OK to call owner")?
- billing_compliance [choice: compliant / partial / noncompliant /
  not_applicable]: were charges/advance charges approved and documented
  the way the seller's billing instructions require (e.g. dollar-threshold
  approvals, itemized breakdowns, GM sign-off)?
- pickup_dispatch_compliance [choice: compliant / partial / noncompliant /
  not_applicable]: did arranging pickup follow the seller's dispatch
  instructions (e.g. getting quotes for non-standard tows, contacting the
  pickup location via allowed methods)?
- overall_compliance_severity [score: no deviation / minor / major]: a
  single overall read on how far the lot's handling deviated from the
  seller's standing instructions.

Use the domain background below only to help you interpret these dimensions
correctly (e.g. action codes, stage meanings) — do not repeat it verbatim.

--- DOMAIN BACKGROUND ---
{DOMAIN_CONTEXT}
--- END DOMAIN BACKGROUND ---

Translate Jev's answers into a short, plain-English explanation a compliance
analyst can read in a few seconds. For EACH of the six dimensions:
1. Say in one sentence what the dimension means (use the plain-English
   descriptions above, not jargon).
2. State Jev's answer and what it practically means (not just the raw
   number/probability).
3. Ground the answer in the source: point to the SPECIFIC line(s) or phrase(s)
   in the seller instructions and/or lot notes that most plausibly explain
   why Jev landed on that answer. If nothing in the source obviously
   supports the answer, say so explicitly rather than inventing a reason.
4. Call out low-confidence or close-probability answers as worth a human
   double-check, since Jev is expressing genuine uncertainty there, not
   necessarily a wrong answer.

Do not re-judge compliance yourself or introduce information beyond what's
in the source text. Keep the whole explanation readable — a few sentences
per dimension is enough."""

COMPARE_SYSTEM = """You compare two independent compliance judgments made
about the same Copart lot: one from Jev (TypeSafe's typed, calibrated
System-1 model) and one from Claude (a general-purpose LLM writing free
text). Both were given the same seller instructions and lot notes.

You will be given Jev's raw JSON answers and Claude's free-text verdict.
Produce a short comparison covering:
1. Where the two agree (same conclusion on the same dimension).
2. Where they disagree, and on which specific dimension
   (escalation/title/communication/billing/pickup-dispatch/overall severity).
3. For any disagreement, note whether Jev's confidence/probabilities for
   that dimension were high or low — a low-confidence Jev answer disagreeing
   with Claude is less concerning than a high-confidence one.
4. A one-line takeaway on whether a human reviewer should trust this lot's
   compliance status as-is or look closer.
Be concise and concrete. Do not just restate both verdicts — actually
compare them."""
