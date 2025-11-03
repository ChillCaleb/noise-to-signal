# streamlit_app.py  (put this at project root)
import streamlit as st

# === use the same functions you run from the CLI ===
from main import (
    build_document_from_url,
    build_document_from_text,
    run_nlp,
    run_llm,
)

# UI helpers
from app.ui.components import render_final_html
from app.ui.theme import inject_global_theme

# --- Streamlit setup ---
st.set_page_config(page_title="Noise → Signal", layout="wide")
inject_global_theme()

st.title("Noise → Signal — Input → Final Summary")

user_input = st.text_area(
    "Paste a URL or text:",
    placeholder="https://example.com/article  •• or ••  paste text here",
    height=140,
)

if st.button("Analyze", type="primary"):
    if not user_input or not user_input.strip():
        st.warning("Please paste a URL or some text.")
        st.stop()

    raw = user_input.strip()
    is_url = raw.lower().startswith(("http://", "https://"))

    with st.spinner("Processing…"):
        try:
            # 1) INPUT ➜ DOCUMENT (same as main.py)
            document = (
                build_document_from_url(raw)
                if is_url else
                build_document_from_text(raw)
            )

            # 2) DOCUMENT ➜ ANALYSIS (same as main.py)
            analysis = run_nlp(document)

            # 3) ANALYSIS ➜ FINAL HTML (same as main.py)
            try:
                html = run_llm(analysis, tier="tier3", output_format="html", length="long")
            except TypeError:
                html = run_llm(analysis, tier="tier3", output_format="html", length="short")

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # 4) DISPLAY
    st.subheader("Final Summary")
    render_final_html(html)
