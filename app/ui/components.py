import streamlit as st

# Everything inside st.components is sandboxed (iframe),
# so we include a full dark theme CSS reset INSIDE the iframe.
_IFRAME_CSS = """
<style>
  :root {
    --bg: #000000;
    --text: #FFFFFF;
    --muted: #CCCCCC;
    --accent: #FFFFFF;
    --border: #1e1e1e;
  }
  html, body {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Inter, Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 0;
  }
  .ns-container {
    background: var(--bg);
    color: var(--text);
    padding: 32px;
  }
  h1,h2,h3,h4,h5,h6 { color: var(--text); margin: 0 0 12px; }
  p, li, blockquote { color: var(--text); }
  blockquote { border-left: 4px solid var(--border); padding-left: 12px; margin-left: 0; color: var(--muted); }
  a, a:visited { color: var(--accent); text-decoration: underline; }
  hr { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
  ul, ol { padding-left: 22px; }
  code, pre {
    background: #0d0d0d; color: var(--text);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 2px 6px;
  }
  pre { padding: 16px; overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid var(--border); padding: 8px 10px; color: var(--text); }
  th { background: #0d0d0d; }
</style>
"""

def _wrap_html_dark(html: str) -> str:
    return f"""{_IFRAME_CSS}
<div class="ns-container">
{html}
</div>
"""

def render_final_html(html: str, height: int = 900, scrolling: bool = True) -> None:
    st.components.v1.html(_wrap_html_dark(html), height=height, scrolling=scrolling)
