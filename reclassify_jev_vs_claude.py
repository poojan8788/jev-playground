"""
Re-runs ONLY the agreement classification step over the already-fetched
Jev/Claude results in jev_vs_claude_results.json (no new Jev/Claude
compliance calls) — used to add richer per-dimension agreement labels
without re-spending on the compliance checks themselves.
"""

import json
import os

from common import get_claude_token, make_anthropic_client, call_claude

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jev_vs_claude_results.json")

DIMENSIONS = [
    "escalation_followed",
    "title_handling",
    "communication_compliance",
    "billing_compliance",
    "pickup_dispatch_compliance",
    "overall_compliance_severity",
]

CLASSIFY_SYSTEM = """You compare a Jev compliance verdict (typed JSON answers)
against a Claude compliance verdict (free text) for the SAME lot, produced
from the same seller instructions and lot notes. Classify their agreement
BOTH per-dimension AND overall, and return ONLY a JSON object with this
exact shape (no other text):

{
  "overall_bucket": "<aligned | minor_deviation | major_deviation | sharp_disagreement>",
  "overall_reason": "<one sentence>",
  "dimensions": {
    "escalation_followed": "<aligned | minor_deviation | major_deviation | sharp_disagreement>",
    "title_handling": "<...>",
    "communication_compliance": "<...>",
    "billing_compliance": "<...>",
    "pickup_dispatch_compliance": "<...>",
    "overall_compliance_severity": "<...>"
  }
}

Bucket definitions (apply the SAME definitions per-dimension and overall):
- "aligned": both engines reach the same conclusion (both compliant / both
  consistent / both say escalation was followed or not applicable in the
  same way) — no meaningful gap.
- "minor_deviation": both engines agree there's SOME issue, and it's
  minor/low-risk on both sides (e.g. Jev says "partial" and Claude
  describes a small gap, not a serious one) — they still broadly agree,
  just not on "fully compliant."
- "major_deviation": both engines agree there's a real, serious compliance
  problem on this dimension.
- "sharp_disagreement": the two engines land on MEANINGFULLY DIFFERENT
  conclusions from each other on this dimension (e.g. Jev's dominant
  probability/choice points toward noncompliant/major while Claude's text
  concludes compliant/no deviation, or vice versa). This is about
  Jev-vs-Claude disagreeing with EACH OTHER, not about how compliant the
  lot actually is.

For "overall_compliance_severity" specifically: compare Jev's dominant
score level (via its probabilities, not just the raw score number) against
Claude's own stated "Overall_compliance_severity" conclusion in its verdict
text.

Respond with ONLY the JSON object."""


def classify_one(client, jev_answers, claude_verdict):
    prompt = (
        "Jev's raw answers:\n"
        + json.dumps(jev_answers, indent=2)
        + "\n\nClaude's verdict:\n"
        + claude_verdict
    )
    text, usage = call_claude(client, CLASSIFY_SYSTEM, prompt, max_tokens=4096)
    if not text.strip():
        print(f"  (empty text; usage={usage})")
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            print("RAW RESPONSE (no JSON braces found):")
            print(repr(text))
            raise
        return json.loads(text[start : end + 1])


def main():
    with open(OUT_PATH) as f:
        data = json.load(f)

    claude_token = get_claude_token()
    if not claude_token:
        raise SystemExit("No Claude token found (GENIE_AI_TOKEN/COPART_AI_TOKEN env var or .env)")
    client = make_anthropic_client(claude_token)

    for lot in data["lots"]:
        print(f"--- {lot['seller_code']} / lot {lot['lot_number']} ---")
        classification = classify_one(client, lot["jev_answers"], lot["claude_verdict"])
        lot["bucket"] = classification["overall_bucket"]
        lot["bucket_reason"] = classification["overall_reason"]
        lot["dimension_buckets"] = classification["dimensions"]
        print(f"  overall: {lot['bucket']}")
        for dim in DIMENSIONS:
            print(f"    {dim}: {lot['dimension_buckets'].get(dim)}")

    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nUpdated {OUT_PATH}")


if __name__ == "__main__":
    main()
