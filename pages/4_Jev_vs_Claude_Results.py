"""
LOT-CRAWLER — Jev vs Claude Results page.

Static results from running Jev + Claude compliance checks on a fixed
sample of 7 real lots spread across all 6 seller codes (built once by
build_jev_vs_claude_results.py, agreement-classified by
reclassify_jev_vs_claude.py). This page does not call Jev or Claude — it
only visualizes the pre-computed results in jev_vs_claude_results.json.
"""

from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

from common import JEV_VS_CLAUDE_RESULTS

st.title("Jev vs Claude Results")
st.caption(
    "A fixed sample of 7 real lots spread across all 6 seller codes (one "
    "seller code contributes 2 lots), run through both Jev and Claude — "
    "static results, no API calls on this page."
)

lots = JEV_VS_CLAUDE_RESULTS.get("lots", [])
if not lots:
    st.warning(
        "jev_vs_claude_results.json not found or empty. Run "
        "`python3 build_jev_vs_claude_results.py` then "
        "`python3 reclassify_jev_vs_claude.py` to generate it "
        "(requires valid Jev + Claude tokens)."
    )
    st.stop()

BUCKET_ORDER = ["aligned", "minor_deviation", "major_deviation", "sharp_disagreement"]
BUCKET_LABELS = {
    "aligned": "Aligned",
    "minor_deviation": "Minor deviation (both agree, low risk)",
    "major_deviation": "Major deviation (both agree, serious)",
    "sharp_disagreement": "Sharp disagreement (Jev vs Claude differ)",
}
BUCKET_COLORS = {
    "aligned": "#6aa84f",
    "minor_deviation": "#f1c232",
    "major_deviation": "#e06666",
    "sharp_disagreement": "#a64d79",
}
DIMENSIONS = [
    "escalation_followed",
    "title_handling",
    "communication_compliance",
    "billing_compliance",
    "pickup_dispatch_compliance",
    "overall_compliance_severity",
]
DIM_LABELS = {
    "escalation_followed": "Escalation followed",
    "title_handling": "Title handling",
    "communication_compliance": "Communication compliance",
    "billing_compliance": "Billing compliance",
    "pickup_dispatch_compliance": "Pickup/dispatch compliance",
    "overall_compliance_severity": "Overall severity",
}

st.markdown(
    """
Each lot was judged independently by **Jev** (typed `noul`/`choice`/`score`
answers) and **Claude** (free-text verdict), from the same seller
instructions + lot notes. Claude was then asked to classify how the two
engines' answers relate to each other, on every dimension AND overall,
into one of four buckets:

- 🟢 **Aligned** — same conclusion, no meaningful gap.
- 🟡 **Minor deviation** — both agree something's slightly off, low risk.
- 🔴 **Major deviation** — both agree there's a serious compliance problem.
- 🟣 **Sharp disagreement** — Jev and Claude land on genuinely different
  conclusions from EACH OTHER (this is about the two engines disagreeing,
  not about how compliant the lot itself is).
"""
)

st.divider()

# ---------------------------------------------------------------------------
st.header("1. Overall agreement across the 7 lots")

overall_counts = Counter(lot["bucket"] for lot in lots)
overall_df = pd.DataFrame(
    [
        {"Bucket": BUCKET_LABELS[b], "bucket_key": b, "Lots": overall_counts.get(b, 0)}
        for b in BUCKET_ORDER
    ]
)

m_cols = st.columns(4)
for col, b in zip(m_cols, BUCKET_ORDER):
    col.metric(BUCKET_LABELS[b].split(" (")[0], overall_counts.get(b, 0))

overall_chart = (
    alt.Chart(overall_df)
    .mark_bar()
    .encode(
        x=alt.X("Lots:Q", title="Number of lots (out of 7)"),
        y=alt.Y("Bucket:N", sort=BUCKET_ORDER and [BUCKET_LABELS[b] for b in BUCKET_ORDER], title=""),
        color=alt.Color(
            "bucket_key:N",
            scale=alt.Scale(domain=BUCKET_ORDER, range=[BUCKET_COLORS[b] for b in BUCKET_ORDER]),
            legend=None,
        ),
        tooltip=["Bucket", "Lots"],
    )
    .properties(height=200)
)
st.altair_chart(overall_chart, use_container_width=True)

st.caption(
    f"{overall_counts.get('aligned', 0)}/7 lots aligned overall, "
    f"{overall_counts.get('sharp_disagreement', 0)}/7 showed a sharp "
    "overall disagreement between Jev and Claude. Note: 'overall' being a "
    "sharp disagreement doesn't mean every dimension disagreed — see the "
    "per-dimension breakdown below, which is usually where the real signal is."
)

st.divider()

# ---------------------------------------------------------------------------
st.header("2. Agreement broken down by compliance dimension")

st.markdown(
    "This is the more useful view: **which specific dimension** Jev and "
    "Claude tend to agree or clash on, across all 7 lots."
)

dim_rows = []
for lot in lots:
    dim_buckets = lot.get("dimension_buckets", {})
    for dim in DIMENSIONS:
        bucket = dim_buckets.get(dim)
        if bucket:
            dim_rows.append({"Dimension": DIM_LABELS[dim], "dim_key": dim, "bucket_key": bucket, "Bucket": BUCKET_LABELS[bucket]})

dim_df = pd.DataFrame(dim_rows)

dim_chart = (
    alt.Chart(dim_df)
    .mark_bar()
    .encode(
        x=alt.X("count():Q", title="Number of lots (out of 7)"),
        y=alt.Y("Dimension:N", sort=[DIM_LABELS[d] for d in DIMENSIONS], title=""),
        color=alt.Color(
            "bucket_key:N",
            scale=alt.Scale(domain=BUCKET_ORDER, range=[BUCKET_COLORS[b] for b in BUCKET_ORDER]),
            legend=alt.Legend(title="Agreement", labelExpr="datum.label"),
            sort=BUCKET_ORDER,
        ),
        order=alt.Order("bucket_key:N", sort="ascending"),
        tooltip=["Dimension", "Bucket", "count()"],
    )
    .properties(height=280)
)
st.altair_chart(dim_chart, use_container_width=True)

# Per-dimension "sharp disagreement rate" as its own small chart, since
# that's the number most worth calling out.
sharp_rate_rows = []
for dim in DIMENSIONS:
    count = sum(1 for lot in lots if lot.get("dimension_buckets", {}).get(dim) == "sharp_disagreement")
    sharp_rate_rows.append({"Dimension": DIM_LABELS[dim], "Sharp disagreements": count})
sharp_df = pd.DataFrame(sharp_rate_rows)

sharp_chart = (
    alt.Chart(sharp_df)
    .mark_bar(color=BUCKET_COLORS["sharp_disagreement"])
    .encode(
        x=alt.X("Sharp disagreements:Q", title="Lots with a sharp disagreement (out of 7)", scale=alt.Scale(domain=[0, 7])),
        y=alt.Y("Dimension:N", sort="-x", title=""),
        tooltip=["Dimension", "Sharp disagreements"],
    )
    .properties(height=280)
)
st.subheader("Where sharp disagreements concentrate")
st.altair_chart(sharp_chart, use_container_width=True)
most_disagreement_dim = max(sharp_rate_rows, key=lambda r: r["Sharp disagreements"])
st.caption(
    f"**{most_disagreement_dim['Dimension']}** had the most sharp "
    f"disagreements ({most_disagreement_dim['Sharp disagreements']}/7 lots) "
    "— worth a closer look if choosing which dimension to trust Jev's "
    "typed answer on unsupervised."
)

st.divider()

# ---------------------------------------------------------------------------
st.header("3. Jev's severity score vs Claude's stated overall conclusion")

st.markdown(
    "Jev's `overall_compliance_severity` is a `score` type — it returns a "
    "raw score (roughly 0=no deviation, 1=minor, 2=major) plus a "
    "probability per level. Plotting Jev's raw score against whether "
    "Claude and Jev ultimately agreed shows whether disagreement clusters "
    "at any particular severity level."
)

sev_rows = []
for lot in lots:
    sev = lot["jev_answers"].get("overall_compliance_severity", {})
    sev_rows.append(
        {
            "Lot": f"{lot['seller_code']} / {lot['lot_number']}",
            "Jev severity score": sev.get("score", 0),
            "Jev confidence": sev.get("confidence", 0),
            "Agreement": BUCKET_LABELS[lot.get("dimension_buckets", {}).get("overall_compliance_severity", lot["bucket"])],
            "bucket_key": lot.get("dimension_buckets", {}).get("overall_compliance_severity", lot["bucket"]),
        }
    )
sev_df = pd.DataFrame(sev_rows)

sev_chart = (
    alt.Chart(sev_df)
    .mark_circle(size=200)
    .encode(
        x=alt.X("Jev severity score:Q", scale=alt.Scale(domain=[0, 2]), title="Jev overall_compliance_severity score (0=none, 2=major)"),
        y=alt.Y("Jev confidence:Q", scale=alt.Scale(domain=[0, 1]), title="Jev's confidence in that score"),
        color=alt.Color(
            "bucket_key:N",
            scale=alt.Scale(domain=BUCKET_ORDER, range=[BUCKET_COLORS[b] for b in BUCKET_ORDER]),
            legend=alt.Legend(title="Agreement w/ Claude"),
        ),
        tooltip=["Lot", "Jev severity score", "Jev confidence", "Agreement"],
    )
    .properties(height=320)
)
st.altair_chart(sev_chart, use_container_width=True)
st.caption(
    "Each point is one lot. Points further right = Jev leaned toward "
    "'major deviation'; points higher up = Jev was more confident in that "
    "score. If disagreement points cluster at low confidence, that's Jev "
    "correctly flagging its own uncertainty rather than being simply wrong."
)

st.divider()

# ---------------------------------------------------------------------------
st.header("4. Per-lot detail")

for lot in lots:
    header = (
        f"{lot['seller_code']} ({lot['seller_name']}) — lot {lot['lot_number']}, "
        f"stage {lot['lot_stage']} — overall: {BUCKET_LABELS[lot['bucket']]}"
    )
    with st.expander(header):
        st.caption(lot.get("bucket_reason", ""))

        dim_table_rows = []
        for dim in DIMENSIONS:
            jev_ans = lot["jev_answers"].get(dim, {})
            if jev_ans.get("type") == "noul":
                jev_summary = f"noul = {jev_ans.get('noul')}"
            elif jev_ans.get("type") == "choice":
                jev_summary = f"{jev_ans.get('choice')} (confidence {jev_ans.get('confidence')})"
            elif jev_ans.get("type") == "score":
                jev_summary = f"score = {jev_ans.get('score')} (confidence {jev_ans.get('confidence')})"
            else:
                jev_summary = "—"
            dim_table_rows.append(
                {
                    "Dimension": DIM_LABELS[dim],
                    "Jev's answer": jev_summary,
                    "Agreement w/ Claude": BUCKET_LABELS.get(
                        lot.get("dimension_buckets", {}).get(dim), "—"
                    ),
                }
            )
        st.table(dim_table_rows)

        st.markdown("**Claude's full verdict:**")
        st.markdown(lot["claude_verdict"])

        with st.expander("Raw Jev answers (JSON)"):
            st.json(lot["jev_answers"])

st.divider()
st.caption(
    "Sample of 7 lots only — enough to illustrate the kind of "
    "agreement/disagreement pattern to expect, not a statistically "
    "representative benchmark. Re-run build_jev_vs_claude_results.py + "
    "reclassify_jev_vs_claude.py with a larger/different sample to refresh "
    "this page."
)
