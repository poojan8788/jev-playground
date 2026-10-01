"""
One-off script: runs Jev + Claude compliance checks for a fixed sample of 7
real lots (spread across all 6 seller codes) and writes the results to
jev_vs_claude_results.json, so the "Jev vs Claude Results" Streamlit page can
show static agreement/deviation stats and charts without calling either API
at view time.

Run again only if you want to refresh the sample (e.g. more lots, different
lots, or after JEV_QUESTIONS/CLAUDE_JUDGE_SYSTEM changes):
    python3 build_jev_vs_claude_results.py
"""

import json
import os

from common import (
    DOMAIN_CONTEXT,
    LOTS_DATASET,
    JEV_QUESTIONS,
    CLAUDE_JUDGE_SYSTEM,
    format_code_glossary,
    get_token,
    get_claude_token,
    make_anthropic_client,
    call_claude,
    call_jev,
)

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jev_vs_claude_results.json")

# 7 lots hand-picked to spread across all 6 seller codes (one extra from
# U004 for a second title-stage example) and across a mix of lot stages.
SAMPLE_LOTS = [
    ("GFLD", "71243676"),
    ("GVIC", "71017256"),
    ("SZ94", "70430216"),
    ("S841", "70280716"),
    ("S859", "70664196"),
    ("U004", "70867816"),
    ("U004", "39134344"),
]


def build_verdict_text_answers(claude_text):
    """We keep Claude's verdict as free text (that's its native output) —
    the comparison/severity classification happens separately below by
    asking Claude itself to classify agreement, since Claude's answer isn't
    typed like Jev's."""
    return claude_text


CLASSIFY_SYSTEM = """You compare a Jev compliance verdict (typed JSON answers)
against a Claude compliance verdict (free text) for the SAME lot. Classify
the overall relationship between them into exactly one of these four
buckets, and return ONLY a JSON object with this exact shape:

{"bucket": "<one of: aligned, minor_deviation, major_deviation, sharp_disagreement>", "reason": "<one sentence>"}

Bucket definitions:
- "aligned": Jev and Claude reach the same overall compliance conclusion
  (both suggest no deviation / fully compliant), including cases where Jev's
  overall_compliance_severity says "no deviation" and Claude's verdict
  agrees.
- "minor_deviation": both engines agree there's SOME deviation, and it's
  minor/low-risk on both sides (e.g. Jev's overall_compliance_severity says
  "minor" and Claude describes a small compliance gap, not a major one).
- "major_deviation": both engines agree there's a real, major compliance
  problem (e.g. Jev's overall_compliance_severity says "major" and Claude
  also flags a significant compliance failure).
- "sharp_disagreement": the two engines land on meaningfully DIFFERENT
  conclusions from each other (e.g. Jev says no deviation but Claude flags a
  major violation, or vice versa; or they disagree on a specific dimension
  like title_handling or escalation_followed in a way that would change what
  a human reviewer does next).

Respond with ONLY the JSON object, no other text."""


def main():
    jev_token = get_token()
    claude_token = get_claude_token()
    if not jev_token:
        raise SystemExit("No Jev token found (COPART_AI_TOKEN env var or .env)")
    if not claude_token:
        raise SystemExit("No Claude token found (GENIE_AI_TOKEN/COPART_AI_TOKEN env var or .env)")

    client = make_anthropic_client(claude_token)

    results = []
    for slr_cd, lot_number in SAMPLE_LOTS:
        seller_entry = LOTS_DATASET[slr_cd]
        lot_entry = seller_entry["lots"][lot_number]
        seller_instructions = seller_entry["instructions_text"]
        lot_notes = lot_entry["notes_text"]

        print(f"--- {slr_cd} / lot {lot_number} (stage {lot_entry['stage']}) ---")

        code_glossary = format_code_glossary(lot_notes)

        print("  calling Jev...")
        jev_state_text = (
            f"DOMAIN BACKGROUND:\n{DOMAIN_CONTEXT}\n\n"
            + (f"{code_glossary}\n\n" if code_glossary else "")
            + f"SELLER CODE INSTRUCTIONS:\n{seller_instructions}\n\n"
            f"LOT NOTES:\n{lot_notes}"
        )
        jev_result, jev_usage = call_jev(jev_token, jev_state_text, JEV_QUESTIONS)

        print("  calling Claude...")
        claude_user_prompt = (
            (f"{code_glossary}\n\n" if code_glossary else "")
            + f"SELLER CODE INSTRUCTIONS:\n{seller_instructions}\n\n"
            f"LOT NOTES:\n{lot_notes}"
        )
        claude_verdict, claude_usage = call_claude(client, CLAUDE_JUDGE_SYSTEM, claude_user_prompt)

        print("  classifying agreement...")
        jev_answers = jev_result.get("answers", {})
        classify_prompt = (
            "Jev's raw answers:\n"
            + json.dumps(jev_answers, indent=2)
            + "\n\nClaude's verdict:\n"
            + claude_verdict
        )
        classify_text, _classify_usage = call_claude(client, CLASSIFY_SYSTEM, classify_prompt, max_tokens=300)
        try:
            classification = json.loads(classify_text.strip())
        except json.JSONDecodeError:
            start = classify_text.find("{")
            end = classify_text.rfind("}")
            classification = json.loads(classify_text[start : end + 1])

        results.append(
            {
                "seller_code": slr_cd,
                "seller_name": seller_entry["slr_nm"],
                "lot_number": lot_number,
                "lot_stage": lot_entry["stage"],
                "lot_status": lot_entry["status"],
                "jev_answers": jev_answers,
                "claude_verdict": claude_verdict,
                "bucket": classification["bucket"],
                "bucket_reason": classification["reason"],
            }
        )
        print(f"  -> bucket: {classification['bucket']}")

    with open(OUT_PATH, "w") as f:
        json.dump({"lots": results}, f, indent=2)
    print(f"\nWrote {OUT_PATH} ({len(results)} lots)")


if __name__ == "__main__":
    main()
