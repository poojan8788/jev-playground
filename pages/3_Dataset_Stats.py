"""
LOT-CRAWLER — Dataset Stats page.

Static counts describing the real-lot dataset (built by build_dataset.py
from Instructions(Sheet1).csv + jevnotes(Sheet1/Sheet2).csv) and the fixed
question schema sent to Jev on every compliance check. Everything here is
precomputed/static — this page does not call Jev or Claude.
"""

import streamlit as st

from common import DATASET_STATS, LOTS_DATASET, JEV_QUESTIONS
from action_codes import ACTION_CODE_MEANINGS

st.title("Dataset Stats")
st.caption("Static facts about the real-lot dataset and the Jev question schema — no API calls on this page.")

if not DATASET_STATS:
    st.warning(
        "dataset_stats.json not found. Run `python3 build_dataset.py` "
        "(requires the source CSVs in ~/Downloads) to generate it."
    )
    st.stop()

# ---------------------------------------------------------------------------
st.header("1. Lots available in the picker")

total_lots = DATASET_STATS["total_lots"]
seller_count = DATASET_STATS["seller_code_count"]

m1, m2, m3 = st.columns(3)
m1.metric("Total lots", total_lots)
m2.metric("Seller codes", seller_count)
m3.metric("Avg lots / seller code", round(total_lots / seller_count, 1))

lots_per_seller = DATASET_STATS["lots_per_seller"]
st.table(
    [
        {
            "Seller code": slr_cd,
            "Seller company code": info["slr_comp_cd"],
            "Seller name": info["slr_nm"],
            "Lots available": info["lot_count"],
        }
        for slr_cd, info in sorted(lots_per_seller.items())
    ]
)

st.divider()

# ---------------------------------------------------------------------------
st.header("2. Seller code standing instructions")

st.markdown(
    f"""
**{seller_count} seller codes** have standing instructions loaded, each with
the same **4 instruction fields** (from `Instructions(Sheet1).csv`,
`key1`/`value1` rows): `assgn_notes`, `biln_notes`, `dspch_notes`,
`title_notes`. That's
**{DATASET_STATS['source_row_counts']['instructions_csv_field_rows']} total
field rows** in the source sheet
({seller_count} sellers × 4 fields = {seller_count * 4}).
"""
)

st.divider()

# ---------------------------------------------------------------------------
st.header("3. Lot stages & statuses in the dataset")

st.markdown(
    "Every lot in the picker has a `LTLOTSTG` (lot stage number) and a "
    "`Lot status` (human-readable) value, from `jevnotes(Sheet2).csv`. "
    "Distribution across the 95 available lots:"
)

stage_col, status_col = st.columns(2)
with stage_col:
    st.markdown("**By stage number**")
    stage_counts = DATASET_STATS["stage_counts"]
    st.table(
        [
            {"Stage": stage, "Lots": count}
            for stage, count in sorted(stage_counts.items(), key=lambda kv: int(kv[0]))
        ]
    )
with status_col:
    st.markdown("**By status text**")
    status_counts = DATASET_STATS["status_counts"]
    st.table(
        [
            {"Status": status, "Lots": count}
            for status, count in sorted(status_counts.items(), key=lambda kv: -kv[1])
        ]
    )

st.divider()

# ---------------------------------------------------------------------------
st.header("4. Mapping across the source spreadsheets")

st.markdown(
    "The dataset is built by joining three separate exports "
    "(`build_dataset.py`) — this is how many rows existed in each, and how "
    "many made it through the join:"
)

src = DATASET_STATS["source_row_counts"]
c1, c2, c3 = st.columns(3)
c1.metric("Instructions.csv rows", src["instructions_csv_field_rows"], help="key1/value1 field rows across all seller codes")
c2.metric("Lot → seller mapping rows", src["lot_seller_mapping_rows"], help="jevnotes(Sheet2).csv — LTLOTNBR -> LTSLRNBR/stage/status, one row per lot")
c3.metric("Raw note lines", src["raw_note_line_rows"], help="jevnotes(Sheet1).csv — one row per individual note entry, across all lots")

st.markdown(
    f"""
- **{src['lot_seller_mapping_rows']} lots** were mapped to a seller code via
  `jevnotes(Sheet2).csv` (`LTLOTNBR` → `LTSLRNBR`).
- **{src['raw_note_line_rows']:,} individual note lines** across
  `jevnotes(Sheet1).csv` were grouped and sorted chronologically per lot
  (average of {round(src['raw_note_line_rows'] / src['lot_seller_mapping_rows'])} note lines per lot).
- **{DATASET_STATS['skipped_no_instructions']} lots skipped** for having no
  matching seller-code instructions, and
  **{DATASET_STATS['skipped_no_notes']} lots skipped** for having no note
  history — i.e. every mapped lot made it into the final dataset.
"""
)

with st.expander(f"Action-code glossary ({len(ACTION_CODE_MEANINGS)} confirmed codes)"):
    st.caption(
        "Auto-generated note codes with confirmed plain-English meanings "
        "(action_codes.py), cross-referenced from the raw note-line export. "
        "Auto-detected and injected into Jev/Claude prompts whenever a "
        "pasted lot's notes contain one of these codes."
    )
    st.table(
        [
            {"Code": code, "Meaning": meaning}
            for code, meaning in sorted(ACTION_CODE_MEANINGS.items())
        ]
    )

st.divider()

# ---------------------------------------------------------------------------
st.header("5. Questions asked of Jev, and the answer options given")

st.markdown(
    f"""
Jev is asked a fixed set of **{len(JEV_QUESTIONS)} questions** on every
compliance check (`JEV_QUESTIONS` in `common.py`) — this schema is
hand-authored, not derived from the CSV columns. Each question has a type
that determines what kind of answer options (if any) are offered:

- **`noul`** — a single yes/no proposition; Jev returns one probability
  (0-1), no fixed answer list.
- **`choice`** — a fixed, named set of mutually exclusive options; Jev
  returns a probability for each.
- **`score`** — an ordered scale with a legend per level; Jev returns a
  probability per level.
"""
)

for key, q in JEV_QUESTIONS.items():
    with st.container(border=True):
        st.markdown(f"**`{key}`**  ·  type: `{q['type']}`")
        st.markdown(q["instructions"])
        if q["type"] == "noul":
            st.caption("Answer: a single probability (0.0–1.0) that the proposition is true. No fixed option list.")
        elif q["type"] == "choice":
            st.markdown("Answer options:")
            st.table(
                [
                    {"Option": option, "Meaning": meaning}
                    for option, meaning in q["criteria"].items()
                ]
            )
        elif q["type"] == "score":
            st.markdown("Scale levels (ordered):")
            st.table([{"Level": i + 1, "Meaning": level} for i, level in enumerate(q["criteria"])])
