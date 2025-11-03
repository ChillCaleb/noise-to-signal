# app/ui/theme.py
from pathlib import Path
import streamlit as st

def inject_global_theme():
    css_path = Path(__file__).with_name("theme.css")
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
