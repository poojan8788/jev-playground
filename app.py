"""
LOT-CRAWLER — initial prototype

Multipage entry point. st.set_page_config must be the very first Streamlit
command, so this file only wires up navigation — all real page content lives
under pages/. Shared setup (constants, prompts, Jev/Claude helpers) lives in
common.py, imported by each page.
"""

import streamlit as st

from common import APP_NAME

st.set_page_config(page_title=f"{APP_NAME} — Jev vs Claude", layout="wide")

pages = [
    st.Page(
        "pages/1_Compliance_Checker.py",
        title="Compliance Checker",
        icon="🔍",
        default=True,
    ),
    st.Page(
        "pages/2_Scaling_This_Tool.py",
        title="Scaling This Tool",
        icon="📈",
    ),
    st.Page(
        "pages/3_Dataset_Stats.py",
        title="Dataset Stats",
        icon="📊",
    ),
    st.Page(
        "pages/4_Jev_vs_Claude_Results.py",
        title="Jev vs Claude Results",
        icon="⚖️",
    ),
]

nav = st.navigation(pages, position="sidebar")
nav.run()
