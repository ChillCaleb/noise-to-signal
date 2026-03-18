import streamlit as st

from app.ui.evaluation_view import render_evaluation_view
from app.ui.theme import inject_global_theme

st.set_page_config(page_title="Evaluation", layout="wide")
inject_global_theme()
render_evaluation_view()
