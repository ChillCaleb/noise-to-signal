import streamlit as st

from main import (
    build_document_from_text,
    build_document_from_url,
    run_llm,
    run_nlp,
)
from app.ui.components import render_final_html
from app.ui.theme import inject_global_theme

st.set_page_config(page_title="Summary", layout="wide")
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
            document = (
                build_document_from_url(raw)
                if is_url else
                build_document_from_text(raw)
            )
            analysis = run_nlp(document)
            try:
                html = run_llm(analysis, tier="tier3", output_format="html", length="long")
            except TypeError:
                html = run_llm(analysis, tier="tier3", output_format="html", length="short")
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.stop()

    st.subheader("Final Summary")
    render_final_html(html)
