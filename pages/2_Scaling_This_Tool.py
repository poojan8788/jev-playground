"""
LOT-CRAWLER — Scaling This Tool page.

Proposes a RAG-based architecture for scaling the compliance-checker beyond
today's "stuff everything into the prompt" approach, using Jev as a
reranker. This is a PROPOSAL ONLY — nothing on this page is implemented in
the running app; it exists to explain the idea and get feedback on it.
"""

import streamlit as st

from common import APP_NAME

st.title(f"{APP_NAME} — Scaling This Tool")
st.caption("A proposal, not (yet) an implementation")

st.info(
    "Nothing on this page is wired up in the app today. This is an "
    "architecture proposal for how the Compliance Checker could evolve as "
    "the number of seller codes and lots grows — written up here so it's "
    "easy to review, discuss, and revisit."
)

# ---------------------------------------------------------------------------
st.header("1. What the tool does today")

st.markdown(
    """
Right now, every compliance check works the same way, no matter how many
seller codes or lots exist:

- The **entire** `domain_context.md` glossary (lot stages, title handling,
  action codes, ~230 lines) is pasted into the prompt.
- The **one** seller code's standing instructions you picked are pasted in.
- The **one** lot's note history you picked is pasted in.
- Jev and Claude each judge that single lot, from scratch, with no memory
  of any other lot they've ever judged.

This works well today because everything fits comfortably in a single
prompt — 6 seller codes, 95 lots, one glossary file. **The problem is that
none of this scales.** If this became a real tool used across Copart's full
seller base (thousands of seller codes, millions of lots), two things break
at once:
"""
)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown(
        """
**Problem A — the glossary/instructions won't fit**

You can't paste "all seller instructions" into one prompt once there are
thousands of seller codes. Even today's single `domain_context.md` file
is already a hand-curated summary, not the full source material — at real
scale, the *relevant slice* of context has to be found, not pasted whole.
"""
    )
with col_b:
    st.markdown(
        """
**Problem B — every lot is judged "cold"**

Jev and Claude have no way to say "this looks like the 40 other lots we've
already judged for this seller code, and here's how those turned out."
Every single lot re-derives the same judgment from first principles, even
when near-identical situations have been judged a hundred times before.
"""
    )

st.divider()

# ---------------------------------------------------------------------------
st.header("2. The core idea: stop pasting everything, start retrieving")

st.markdown(
    """
This is a classic **RAG** (Retrieval-Augmented Generation) problem: instead
of stuffing all possibly-relevant context into every prompt, you store it
once in a searchable index, and pull out only the small slice that's
actually relevant to *this* lot, on demand.

RAG normally has two stages — retrieve, then generate. The idea explored
here (inspired by
[TypeSafe's "Jev as a reranker" write-up](https://www.mindstudio.ai/blog/jev-reranker-rag))
is to add a **middle stage**: use Jev — which is cheap, fast, and answers
narrow yes/no or multiple-choice questions with a calibrated confidence
score — to re-rank a first pass of retrieved candidates *before* handing
only the best few to Claude. Three stages instead of two:
"""
)

st.markdown(
    """
| Stage | Question it answers | Who/what does it |
|---|---|---|
| **1. Retrieve** | "What's roughly relevant?" | A vector search over embeddings — cheap, fast, but imprecise (a bag-of-candidates, not a verdict) |
| **2. Rerank** | "Which of these candidates actually matters?" | **Jev** — asks a narrow, steerable question per candidate ("is this precedent actually relevant to this lot?") and returns a calibrated probability, without retraining anything |
| **3. Generate** | "Given the best evidence, what's the verdict?" | **Claude** — reasons in free text over only the top-ranked, now-trustworthy evidence, and writes the explainable verdict |
"""
)

st.divider()

# ---------------------------------------------------------------------------
st.header("3. Two places this applies in THIS tool")

st.subheader("3a. Seller-instruction retrieval (scaling the glossary)")
st.markdown(
    """
**Today:** `domain_context.md` (one static file) + the one seller code's
instructions you picked are pasted in full, every time.

**At scale:** embed `domain_context.md` in chunks (one embedding per
concept — "title handling," "release issues," "escalation," etc.) plus
every seller code's standing instructions, into a vector store. For a given
lot:
1. **Retrieve** the handful of domain-context chunks and the one seller's
   instructions whose embeddings are closest to this lot's notes.
2. **Jev-rerank** those chunks — "is this chunk actually relevant to
   judging *this* lot's notes?" — to drop near-misses a pure similarity
   search would keep (e.g. a chunk about salvage titles retrieved for a
   lot that's still at pickup stage).
3. **Generate** the verdict with Claude, using only the surviving,
   Jev-approved chunks — a much smaller, more targeted prompt than
   "paste the whole glossary."
"""
)

st.subheader("3b. Precedent retrieval (learning from past lots)")
st.markdown(
    """
**Today:** each lot is judged with zero awareness of any other lot ever
judged for that seller code.

**At scale:** embed every past lot's (seller instructions + notes + final
verdict) as it gets judged, building up a growing precedent library. For a
new lot:
1. **Retrieve** the K most similar past lots for the same seller code
   (by embedding similarity on the notes).
2. **Jev-rerank** those K candidates by asking a narrow question per
   candidate — "does this past lot's situation actually match the current
   lot's, closely enough to be useful precedent?" — filtering down to the
   few genuinely comparable cases (not just textually similar ones).
3. **Generate** the verdict with Claude, feeding the top 2-3 precedents in
   as few-shot grounding ("here's how 3 near-identical past lots for this
   seller were judged, and why") instead of judging cold every time.

This is the same reranker pattern as 3a, applied to precedent lots instead
of glossary chunks.
"""
)

st.divider()

# ---------------------------------------------------------------------------
st.header("4. Why Jev specifically fits the reranker role")

st.markdown(
    """
Reranking doesn't strictly require Jev — any model can be asked "is this
relevant?" — but Jev's specific design maps unusually well onto this job:

- **Steerable without retraining.** Jev's `criteria` field (the same
  mechanism this app already uses for `title_handling`, `billing_compliance`,
  etc.) lets you change what "relevant" means per use case just by editing
  the prompt/criteria — no fine-tuning needed to adapt the reranker to a
  new seller code or a new kind of precedent match.
- **Calibrated, not just a label.** Jev returns an actual probability, not
  just "relevant"/"not relevant." That means the pipeline can set a
  threshold (e.g. only keep candidates above 0.7) instead of trusting a
  binary judgment blindly — and low-confidence rerank scores can be
  surfaced to a human, exactly like this app already does for the
  compliance verdicts themselves.
- **Cheap and fast at volume.** Reranking is a high-volume, low-complexity
  step — every retrieved candidate needs a quick relevance check. Jev's
  non-autoregressive architecture (a single forward pass instead of
  sequential token generation — the same reason it returns in ~1s vs
  Claude's ~20s in this app's own usage panel) makes checking dozens of
  candidates per lot cheap enough to do routinely, where doing the same
  volume of checks with a full free-text LLM call each would be slow and
  costly.
- **Concurrency.** The source write-up this idea is drawn from reports a
  batch-latency improvement from ~40s to ~7.6s when many rerank calls run
  concurrently — relevant here because reranking candidates for a single
  lot (glossary chunks, or precedent lots) is an embarrassingly parallel
  batch of independent yes/no questions.
"""
)

st.divider()

# ---------------------------------------------------------------------------
st.header("5. Proposed architecture diagram")

tab_today, tab_proposed = st.tabs(["Today (no retrieval)", "Proposed (retrieve → Jev rerank → Claude)"])

with tab_today:
    st.graphviz_chart(
        """
        digraph today {
            rankdir=LR;
            node [shape=box, style="rounded,filled", fontname="Helvetica", fillcolor="#EFEFEF"];

            notes [label="Lot notes\\n(pasted, one lot)"];
            instr [label="Seller instructions\\n(pasted, one seller code)"];
            glossary [label="domain_context.md\\n(entire file, every run)"];

            subgraph cluster_prompt {
                label="Single prompt, every time";
                style=dashed;
                jev [label="Jev", fillcolor="#CDE7FF"];
                claude [label="Claude", fillcolor="#FFE7B3"];
            }

            verdict [label="Verdict\\n(judged cold,\\nno memory of past lots)", fillcolor="#D9EAD3"];

            notes -> jev;
            instr -> jev;
            glossary -> jev;
            notes -> claude;
            instr -> claude;
            glossary -> claude;
            jev -> verdict;
            claude -> verdict;
        }
        """
    )
    st.caption(
        "Today: everything is pasted into every prompt. Fine at 6 seller "
        "codes / 95 lots — doesn't scale to thousands of seller codes or "
        "millions of judged lots."
    )

with tab_proposed:
    st.graphviz_chart(
        """
        digraph proposed {
            rankdir=LR;
            node [shape=box, style="rounded,filled", fontname="Helvetica", fillcolor="#EFEFEF"];

            notes [label="New lot's notes\\n+ seller code"];

            subgraph cluster_store {
                label="Vector store (built once, grows over time)";
                style=dashed;
                glossary_emb [label="Embedded domain-context\\nchunks", fillcolor="#F4CCCC"];
                instr_emb [label="Embedded seller\\ninstructions (all sellers)", fillcolor="#F4CCCC"];
                precedent_emb [label="Embedded past lots\\n(notes + verdict)", fillcolor="#F4CCCC"];
            }

            retrieve [label="Stage 1: Retrieve\\n(vector similarity search)", fillcolor="#D0E0E3"];

            subgraph cluster_rerank {
                label="Stage 2: Rerank";
                style=dashed;
                jev_rerank [label="Jev\\n(calibrated relevance\\nscore per candidate)", fillcolor="#CDE7FF"];
            }

            filtered [label="Top-N relevant chunks\\n+ top-N precedent lots\\n(small, targeted)", fillcolor="#D9EAD3"];

            subgraph cluster_generate {
                label="Stage 3: Generate";
                style=dashed;
                claude_gen [label="Claude\\n(verdict + citations,\\nfew-shot grounded)", fillcolor="#FFE7B3"];
            }

            verdict [label="Verdict\\n(grounded in retrieved\\nglossary + real precedent)", fillcolor="#B6D7A8"];

            notes -> retrieve;
            glossary_emb -> retrieve;
            instr_emb -> retrieve;
            precedent_emb -> retrieve;
            retrieve -> jev_rerank [label="candidates"];
            jev_rerank -> filtered;
            filtered -> claude_gen;
            notes -> claude_gen;
            claude_gen -> verdict;
            verdict -> precedent_emb [label="stored back as\\na new precedent", style=dotted, constraint=false];
        }
        """
    )
    st.caption(
        "Proposed: retrieve only what's relevant, let Jev cheaply filter "
        "out near-misses, then let Claude reason over a small, trustworthy "
        "set of evidence. Each judged lot can feed back in as a new "
        "precedent (dotted line), so the system gets more useful over time."
    )

st.divider()

# ---------------------------------------------------------------------------
st.header("6. What this would actually take to build")

st.markdown(
    """
To be concrete about the gap between "this diagram" and "a working system":

1. **An embedding model + vector store.** Something to turn seller
   instructions, domain-context chunks, and past lot notes into vectors,
   plus a place to store/search them (e.g. pgvector, a managed vector DB,
   or even a simple in-memory index at today's small scale).
2. **A precedent-writing step.** Every time a lot gets a final verdict
   (human-confirmed, ideally — not just an LLM's raw first answer), embed
   and store (seller code, notes, verdict) as a new precedent, so the
   library actually grows from real usage instead of staying static.
3. **Jev rerank prompts.** A small library of narrow relevance questions —
   "is this glossary chunk relevant to this lot?", "is this past lot a
   valid precedent for this lot?" — reusing the same `criteria`-based
   question format this app already sends Jev for compliance judging.
4. **A relevance threshold + fallback.** A rule for what happens when
   retrieval + rerank finds *nothing* confidently relevant (e.g. a brand
   new seller code with no precedent yet) — likely: fall back to exactly
   today's "paste the seller's instructions + full glossary" behavior for
   that case, since it's still cheap enough at the individual-lot level.
5. **Evaluation.** A way to check that reranked/retrieved context actually
   improves verdict quality over today's full-context approach, not just
   that it's cheaper — e.g. re-running this app's existing "Compare Jev vs
   Claude" judgment on a held-out set of already-known-good verdicts.

None of this is required for the tool to keep working as a small-scale
proof of concept — it only becomes necessary once the seller/lot volume
outgrows what fits in a single prompt.
"""
)
