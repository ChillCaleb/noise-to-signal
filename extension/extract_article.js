(() => {
  const normalize = (value) => (value || "").replace(/\s+/g, " ").trim();

  const selectedText = normalize(window.getSelection ? window.getSelection().toString() : "");
  const candidates = [
    ...document.querySelectorAll(
      "article, main, [role='main'], .article, .post, .entry-content, .story, .content"
    )
  ];

  let bestText = "";
  for (const node of candidates) {
    const text = normalize(node.innerText);
    if (text.length > bestText.length) {
      bestText = text;
    }
  }

  const pageText = bestText || normalize(document.body ? document.body.innerText : "");
  const text = selectedText || pageText;
  const canonical = document.querySelector("link[rel='canonical']");

  return {
    title: normalize(document.title),
    url: canonical && canonical.href ? canonical.href : window.location.href,
    text: text.slice(0, 60000),
    selected: Boolean(selectedText)
  };
})();

