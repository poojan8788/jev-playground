"""
LOT-CRAWLER — Compliance Checker page.

Jev vs Claude lot-notes compliance checking UI. All shared setup (constants,
prompts, Jev/Claude call helpers, domain context/dataset loading) lives in
common.py.
"""

import json

import streamlit as st

from common import (
    APP_NAME,
    APP_TAGLINE,
    DOMAIN_CONTEXT,
    DOMAIN_CONTEXT_PATH,
    LOTS_DATASET,
    LOG_FILE,
    CLAUDE_GATEWAY,
    GATEWAYS,
    JEV_QUESTIONS,
    CLAUDE_JUDGE_SYSTEM,
    STAGE_SUMMARY_SYSTEM,
    JEV_EXPLAIN_SYSTEM,
    COMPARE_SYSTEM,
    CLAUDE_PRICE_PER_MTOK_INPUT,
    CLAUDE_PRICE_PER_MTOK_OUTPUT,
    format_code_glossary,
    get_token,
    get_claude_token,
    make_anthropic_client,
    call_claude,
    call_jev,
    logger,
)

st.title(f"{APP_NAME} — {APP_TAGLINE}")
st.caption("Jev vs Claude — Lot Notes Compliance Checker")

with st.expander("What is this tool?", expanded=True):
    st.markdown(
        """
A lot (car/asset) moves through multiple stages before it gets auctioned off.
At each stage, a lot must satisfy checks/conditions driven by its **seller
code's standing instructions** (assignment, billing, dispatch, and title
notes — configured at the seller/seller-code level, e.g. in g2-ssm, and
copied onto the lot at intake).

This tool lets you:
1. Paste a seller code's standing instructions and a lot's note history.
2. Get an LLM-generated summary of what stage the lot is in and what's
   happened so far.
3. Run **Jev** (TypeSafe AI's non-autoregressive System-1 model) to get fast,
   typed compliance judgments (`noul` / `choice` / `score`) against the
   seller's instructions.
4. Run **Claude** on the same inputs to get a free-text verdict, so you can
   compare Jev's typed output against a general-purpose LLM's reasoning.
5. Ask Claude to **explain Jev's decision** in plain English, since raw
   `noul` / `choice` / `score` JSON isn't easy to read at a glance.
6. Ask Claude to **compare Jev vs Claude's judgments** and flag agreements,
   disagreements, and how much to trust each.
7. See **token usage, latency, and estimated cost** side by side for Jev vs
   Claude on this same lot.

Both Jev and Claude are also given a static **domain background** on Copart
lot stages, title handling, release issues, and note action codes
(researched from the g2-ssm and g2-seller repos — see the expander below)
on every run, so they judge compliance with real domain context instead of
just the raw pasted text.

This is exploratory — the goal is to judge whether Jev's typed-decision
approach is a good match for this compliance-checking use case, side by
side with Claude. See the **Scaling This Tool** page in the sidebar for how
this approach could evolve as the number of sellers/lots grows.
        """
    )

with st.expander("Domain background sent to Jev & Claude on every run"):
    st.caption(f"Loaded from `{DOMAIN_CONTEXT_PATH}` — edit that file to refine it.")
    if DOMAIN_CONTEXT:
        st.markdown(DOMAIN_CONTEXT)
    else:
        st.warning("domain_context.md not found or empty — running without domain context.")

with st.sidebar:
    st.header("Debug")
    st.caption(f"Logging this run to:\n`{LOG_FILE}`")
    st.caption(f"Claude gateway: `{CLAUDE_GATEWAY}` (set CLAUDE_GATEWAY=router|genie)")

    st.header("Credentials")
    st.text_input(
        "Jev token override (optional)",
        type="password",
        key="token_override",
        help="Falls back to COPART_AI_TOKEN env var if left blank. "
        "Used for Jev calls via the Copart ops-portal router.",
    )
    st.text_input(
        f"Claude token override (optional, gateway={CLAUDE_GATEWAY})",
        type="password",
        key="claude_token_override",
        help=f"Falls back to {GATEWAYS[CLAUDE_GATEWAY]['token_env']} env var if left "
        "blank. Used for Claude calls via the selected gateway.",
    )
    st.caption(
        "Tokens are kept only in this session's memory, never written to disk."
    )

if LOTS_DATASET:
    st.subheader("Load a real lot (optional)")
    picker_col1, picker_col2, picker_col3 = st.columns([1, 1, 1])
    with picker_col1:
        seller_options = sorted(LOTS_DATASET.keys())
        selected_seller = st.selectbox(
            "Seller code", options=["-- select --"] + seller_options
        )
    with picker_col2:
        if selected_seller != "-- select --":
            lot_options = sorted(LOTS_DATASET[selected_seller]["lots"].keys())
            selected_lot = st.selectbox("Lot number", options=["-- select --"] + lot_options)
        else:
            selected_lot = "-- select --"
    with picker_col3:
        st.write("")
        st.write("")
        load_clicked = st.button("Load this lot")

    if load_clicked:
        if selected_seller == "-- select --" or selected_lot == "-- select --":
            st.warning("Pick both a seller code and a lot number first.")
        else:
            seller_entry = LOTS_DATASET[selected_seller]
            lot_entry = seller_entry["lots"][selected_lot]
            st.session_state["seller_instructions_text"] = seller_entry["instructions_text"]
            st.session_state["lot_notes_text"] = lot_entry["notes_text"]
            st.success(
                f"Loaded lot {selected_lot} ({selected_seller}, stage {lot_entry['stage']}, "
                f"{lot_entry['note_count']} notes)"
            )

    total_lots = sum(len(v["lots"]) for v in LOTS_DATASET.values())
    st.caption(
        f"{total_lots} real lots available across {len(LOTS_DATASET)} seller codes — "
        f"built from Instructions/jevnotes CSV exports via build_dataset.py. "
        f"Re-run that script if the source CSVs change."
    )
    st.divider()

col1, col2 = st.columns(2)
with col1:
    seller_instructions = st.text_area(
        "Seller code instructions (free text)",
        height=220,
        placeholder="Paste the seller code's assgn_notes / biln_notes / dspch_notes / title_notes here...",
        key="seller_instructions_text",
    )
with col2:
    lot_notes = st.text_area(
        "Lot notes (free text)",
        height=220,
        placeholder="Paste the lot's note history here...",
        key="lot_notes_text",
    )

st.divider()

for key in (
    "stage_summary",
    "jev_result",
    "jev_usage",
    "claude_result",
    "claude_usage",
    "jev_explanation",
    "comparison",
):
    if key not in st.session_state:
        st.session_state[key] = None

summarize_clicked = st.button("Summarize lot stage (Claude)", type="secondary")

if summarize_clicked:
    if not lot_notes.strip():
        st.warning("Paste some lot notes first.")
    else:
        token = get_claude_token()
        if not token:
            st.error(
                f"No Claude token found. Set {GATEWAYS[CLAUDE_GATEWAY]['token_env']} "
                "or paste one in the sidebar."
            )
        else:
            with st.spinner("Summarizing lot stage..."):
                try:
                    client = make_anthropic_client(token)
                    summary, _usage = call_claude(
                        client,
                        STAGE_SUMMARY_SYSTEM,
                        f"Lot notes:\n{lot_notes}",
                    )
                    st.session_state.stage_summary = summary
                except Exception as e:
                    logger.exception("Claude summarize call failed")
                    st.error(f"Claude call failed: {e}. See log file: {LOG_FILE}")

if st.session_state.stage_summary:
    st.subheader("Lot stage summary")
    st.markdown(st.session_state.stage_summary)

st.divider()

run_col1, run_col2 = st.columns(2)

with run_col1:
    st.subheader("Jev")
    if st.button("Run Jev compliance check"):
        if not seller_instructions.strip() or not lot_notes.strip():
            st.warning("Paste both seller instructions and lot notes first.")
        else:
            token = get_token()
            if not token:
                st.error("No token found. Set COPART_AI_TOKEN or paste one in the sidebar.")
            else:
                code_glossary = format_code_glossary(lot_notes)
                state_text = (
                    f"DOMAIN BACKGROUND:\n{DOMAIN_CONTEXT}\n\n"
                    + (f"{code_glossary}\n\n" if code_glossary else "")
                    + f"SELLER CODE INSTRUCTIONS:\n{seller_instructions}\n\n"
                    f"LOT NOTES:\n{lot_notes}"
                )
                with st.spinner("Calling Jev..."):
                    try:
                        result, usage = call_jev(token, state_text, JEV_QUESTIONS)
                        st.session_state.jev_result = result
                        st.session_state.jev_usage = usage
                    except Exception as e:
                        logger.exception("Jev call failed")
                        st.error(f"Jev call failed: {e}. See log file: {LOG_FILE}")

    if st.session_state.jev_result:
        answers = st.session_state.jev_result.get("answers", {})
        for key, ans in answers.items():
            st.markdown(f"**{key}**")
            st.json(ans)
        with st.expander("Raw Jev response"):
            st.json(st.session_state.jev_result)

with run_col2:
    st.subheader("Claude")
    if st.button("Run Claude compliance check"):
        if not seller_instructions.strip() or not lot_notes.strip():
            st.warning("Paste both seller instructions and lot notes first.")
        else:
            token = get_claude_token()
            if not token:
                st.error(
                    f"No Claude token found. Set {GATEWAYS[CLAUDE_GATEWAY]['token_env']} "
                    "or paste one in the sidebar."
                )
            else:
                code_glossary = format_code_glossary(lot_notes)
                user_prompt = (
                    (f"{code_glossary}\n\n" if code_glossary else "")
                    + f"SELLER CODE INSTRUCTIONS:\n{seller_instructions}\n\n"
                    f"LOT NOTES:\n{lot_notes}"
                )
                with st.spinner("Calling Claude..."):
                    try:
                        client = make_anthropic_client(token)
                        verdict, usage = call_claude(
                            client, CLAUDE_JUDGE_SYSTEM, user_prompt
                        )
                        st.session_state.claude_result = verdict
                        st.session_state.claude_usage = usage
                    except Exception as e:
                        logger.exception("Claude compliance call failed")
                        st.error(f"Claude call failed: {e}. See log file: {LOG_FILE}")

    if st.session_state.claude_result:
        st.markdown(st.session_state.claude_result)

st.divider()

explain_col, compare_col = st.columns(2)

with explain_col:
    st.subheader("Explain Jev's decision")
    if st.button("Summarize Jev's decision (Claude)"):
        if not st.session_state.jev_result:
            st.warning("Run Jev first.")
        else:
            token = get_claude_token()
            if not token:
                st.error(
                    f"No Claude token found. Set {GATEWAYS[CLAUDE_GATEWAY]['token_env']} "
                    "or paste one in the sidebar."
                )
            else:
                with st.spinner("Asking Claude to explain Jev's answers..."):
                    try:
                        client = make_anthropic_client(token)
                        explanation, _usage = call_claude(
                            client,
                            JEV_EXPLAIN_SYSTEM,
                            "Jev's raw answers:\n"
                            + json.dumps(
                                st.session_state.jev_result.get("answers", {}),
                                indent=2,
                            )
                            + "\n\nSELLER CODE INSTRUCTIONS:\n"
                            + seller_instructions
                            + "\n\nLOT NOTES:\n"
                            + lot_notes,
                        )
                        st.session_state.jev_explanation = explanation
                    except Exception as e:
                        logger.exception("Jev explanation call failed")
                        st.error(f"Claude call failed: {e}. See log file: {LOG_FILE}")

    if st.session_state.jev_explanation:
        st.markdown(st.session_state.jev_explanation)

with compare_col:
    st.subheader("Compare Jev vs Claude")
    if st.button("Compare judgments (Claude)"):
        if not st.session_state.jev_result or not st.session_state.claude_result:
            st.warning("Run both Jev and Claude compliance checks first.")
        else:
            token = get_claude_token()
            if not token:
                st.error(
                    f"No Claude token found. Set {GATEWAYS[CLAUDE_GATEWAY]['token_env']} "
                    "or paste one in the sidebar."
                )
            else:
                with st.spinner("Asking Claude to compare both verdicts..."):
                    try:
                        client = make_anthropic_client(token)
                        comparison, _usage = call_claude(
                            client,
                            COMPARE_SYSTEM,
                            "Jev's raw answers:\n"
                            + json.dumps(
                                st.session_state.jev_result.get("answers", {}),
                                indent=2,
                            )
                            + "\n\nClaude's verdict:\n"
                            + st.session_state.claude_result,
                        )
                        st.session_state.comparison = comparison
                    except Exception as e:
                        logger.exception("Comparison call failed")
                        st.error(f"Claude call failed: {e}. See log file: {LOG_FILE}")

    if st.session_state.comparison:
        st.markdown(st.session_state.comparison)

st.divider()

st.subheader("Usage, latency & cost")
if st.button("Show token usage / time / cost (Jev vs Claude)"):
    if not st.session_state.jev_usage and not st.session_state.claude_usage:
        st.warning("Run at least one of Jev or Claude compliance checks first.")
    else:
        rows = []
        if st.session_state.jev_usage:
            u = st.session_state.jev_usage
            rows.append(
                {
                    "Engine": "Jev",
                    "Input tokens": u["input_tokens"],
                    "Output tokens": u["output_tokens"],
                    "Time (sec)": round(u["elapsed_sec"], 2),
                    "Cost (USD)": round(u["cost"], 6),
                }
            )
        if st.session_state.claude_usage:
            u = st.session_state.claude_usage
            rows.append(
                {
                    "Engine": "Claude",
                    "Input tokens": u["input_tokens"],
                    "Output tokens": u["output_tokens"]
                    - u.get("thinking_tokens", 0),
                    "Time (sec)": round(u["elapsed_sec"], 2),
                    "Cost (USD)": round(u["estimated_cost"], 6),
                }
            )
        st.table(rows)
        if st.session_state.claude_usage:
            st.caption(
                "Claude cost is an *estimate* "
                f"(${CLAUDE_PRICE_PER_MTOK_INPUT}/Mtok in, "
                f"${CLAUDE_PRICE_PER_MTOK_OUTPUT}/Mtok out — override with "
                "CLAUDE_PRICE_INPUT_PER_MTOK / CLAUDE_PRICE_OUTPUT_PER_MTOK env "
                "vars). Jev cost comes directly from its response. Claude's "
                f"output tokens above exclude {st.session_state.claude_usage.get('thinking_tokens', 0)} "
                "extended-thinking tokens, which Claude still generates (and "
                "which cost time) but which never became the visible verdict."
            )
        with st.expander("Why aren't Jev's output tokens 0, and why do input tokens differ?"):
            st.markdown(
                """
**Jev's output tokens aren't 0.** "Non-autoregressive" describes *how* Jev
produces an answer — one forward pass yielding calibrated
probabilities/choices directly, not step-by-step sampling of the next token
like Claude does. It doesn't mean the answer is token-free. Jev's typed
JSON answer (fields, choices, probabilities) still gets serialized and
counted as tokens for usage/billing purposes — that's the ~130 output
tokens you see. The architectural win isn't "0 output tokens," it's that
those tokens are all produced in a single pass instead of ~1,600 sequential
generation steps, which is why Jev returns in ~1s while Claude takes ~20s.

**Jev and Claude show different input token counts for the same pasted
text** for two reasons:
1. **Different tokenizers.** TypeSafe's Jev and Anthropic's Claude use
   different vocabularies, so identical raw text doesn't split into the
   same number of tokens for each.
2. **Different request payloads.** Jev's request bundles the seller
   instructions + lot notes with the compact `JEV_QUESTIONS` schema (short
   keys/criteria). Claude's request carries the same text plus the much
   longer `CLAUDE_JUDGE_SYSTEM` prompt (full-sentence instructions,
   formatting guidance, etc.) as a separate system field — extra tokens Jev's
   request doesn't have an equivalent of.

So the token counts in the table aren't directly apples-to-apples; they
reflect each engine's own tokenizer and prompt-engineering overhead, not
just the shared seller-instructions/lot-notes text.
                """
            )
