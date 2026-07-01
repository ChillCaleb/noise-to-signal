const DEFAULT_API_BASE = "http://127.0.0.1:8000";

const els = {
  apiBase: document.getElementById("apiBase"),
  tier: document.getElementById("tier"),
  length: document.getElementById("length"),
  analyzePage: document.getElementById("analyzePage"),
  analyzeUrl: document.getElementById("analyzeUrl"),
  copySummary: document.getElementById("copySummary"),
  refreshHistory: document.getElementById("refreshHistory"),
  pageMeta: document.getElementById("pageMeta"),
  status: document.getElementById("status"),
  summary: document.getElementById("summary"),
  signals: document.getElementById("signals"),
  historyList: document.getElementById("historyList")
};

let currentResult = null;

function storageGet(keys) {
  return new Promise((resolve) => chrome.storage.sync.get(keys, resolve));
}

function storageSet(values) {
  return new Promise((resolve) => chrome.storage.sync.set(values, resolve));
}

function setStatus(message, type = "") {
  els.status.textContent = message;
  els.status.className = `status ${type}`.trim();
}

function cleanApiBase() {
  return (els.apiBase.value || DEFAULT_API_BASE).replace(/\/+$/, "");
}

async function saveSettings() {
  await storageSet({
    apiBase: cleanApiBase(),
    tier: els.tier.value,
    length: els.length.value
  });
}

async function loadSettings() {
  const settings = await storageGet(["apiBase", "tier", "length"]);
  els.apiBase.value = settings.apiBase || DEFAULT_API_BASE;
  els.tier.value = settings.tier || "tier2";
  els.length.value = settings.length || "medium";
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs && tabs[0] ? tabs[0] : null;
}

async function extractPage() {
  const tab = await getActiveTab();
  if (!tab || !tab.id) {
    throw new Error("No active tab found.");
  }
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["extract_article.js"]
  });
  if (!result || !result.result) {
    throw new Error("Could not read the active page.");
  }
  return {
    title: result.result.title || tab.title || null,
    url: result.result.url || tab.url || null,
    text: result.result.text || "",
    selected: result.result.selected || false
  };
}

async function getUrlOnlyPayload() {
  const tab = await getActiveTab();
  if (!tab || !tab.url) {
    throw new Error("No active tab URL found.");
  }
  return {
    title: tab.title || null,
    url: tab.url,
    text: null
  };
}

function setBusy(isBusy) {
  els.analyzePage.disabled = isBusy;
  els.analyzeUrl.disabled = isBusy;
  els.refreshHistory.disabled = isBusy;
}

async function postJson(path, payload) {
  const response = await fetch(`${cleanApiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with HTTP ${response.status}`);
  }
  return data;
}

async function getJson(path) {
  const response = await fetch(`${cleanApiBase()}${path}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with HTTP ${response.status}`);
  }
  return data;
}

function commaList(values, fallback = "None found") {
  if (!Array.isArray(values) || values.length === 0) {
    return fallback;
  }
  return values.slice(0, 12).join(", ");
}

function addSignal(label, value) {
  const row = document.createElement("div");
  row.className = "signal-row";
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = label;
  dd.textContent = value || "n/a";
  row.append(dt, dd);
  els.signals.append(row);
}

function renderResult(result) {
  currentResult = result;
  els.summary.textContent = result.summary_text || "No summary returned.";
  els.pageMeta.textContent = result.title || result.url || "Analyzed page";

  const analysis = result.analysis || {};
  const facts = analysis.facts || {};
  const entities = facts.entities || {};
  els.signals.textContent = "";
  addSignal("Keywords", commaList(analysis.keywords));
  addSignal("Tickers", commaList(facts.tickers));
  addSignal("Organizations", commaList(entities.ORG));
  addSignal("People", commaList(entities.PERSON));
  addSignal("Money", commaList(facts.money));
  addSignal("Percents", commaList(facts.percents));
  addSignal("Stance", String((analysis.modality || {}).stance_index ?? "n/a"));
}

async function analyze(mode) {
  await saveSettings();
  setBusy(true);
  setStatus(mode === "page" ? "Reading page..." : "Sending URL to backend...");
  try {
    const basePayload = mode === "page" ? await extractPage() : await getUrlOnlyPayload();
    if (mode === "page" && (!basePayload.text || basePayload.text.length < 80)) {
      throw new Error("The page text looked empty. Try URL only.");
    }
    setStatus("Analyzing with backend...");
    const result = await postJson("/api/analyze", {
      title: basePayload.title,
      url: basePayload.url,
      text: basePayload.text,
      tier: els.tier.value,
      output_format: "text",
      length: els.length.value,
      save: true
    });
    renderResult(result);
    setStatus("Analysis complete.", "ok");
    await loadHistory();
  } catch (error) {
    setStatus(error.message || "Analysis failed.", "error");
  } finally {
    setBusy(false);
  }
}

function renderHistory(items) {
  els.historyList.textContent = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.className = "history-item";
    empty.textContent = "No saved runs yet.";
    els.historyList.append(empty);
    return;
  }

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "history-item";
    const button = document.createElement("button");
    const time = document.createElement("time");
    const preview = document.createElement("p");
    button.textContent = item.title || item.url || "Untitled analysis";
    time.textContent = item.created_at || "";
    preview.textContent = item.summary_text || "";
    button.addEventListener("click", () => {
      currentResult = item;
      els.summary.textContent = item.summary_text || "";
      els.pageMeta.textContent = item.title || item.url || "Saved analysis";
      setStatus("Loaded saved summary. Signals are only shown for freshly analyzed pages.", "ok");
    });
    li.append(button, time, preview);
    els.historyList.append(li);
  }
}

async function loadHistory() {
  try {
    const data = await getJson("/api/history?limit=8");
    renderHistory(data.items || []);
  } catch (error) {
    renderHistory([]);
    setStatus(`History unavailable: ${error.message}`, "warn");
  }
}

async function copySummary() {
  const text = currentResult ? currentResult.summary_text : els.summary.textContent;
  if (!text || text === "No summary yet.") {
    setStatus("Nothing to copy yet.", "warn");
    return;
  }
  await navigator.clipboard.writeText(text);
  setStatus("Summary copied.", "ok");
}

els.apiBase.addEventListener("change", saveSettings);
els.tier.addEventListener("change", saveSettings);
els.length.addEventListener("change", saveSettings);
els.analyzePage.addEventListener("click", () => analyze("page"));
els.analyzeUrl.addEventListener("click", () => analyze("url"));
els.copySummary.addEventListener("click", copySummary);
els.refreshHistory.addEventListener("click", loadHistory);

loadSettings().then(loadHistory);
