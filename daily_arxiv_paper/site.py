from __future__ import annotations

import json
import shutil
from pathlib import Path


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily arXiv CV</title>
  <link rel="stylesheet" href="./styles.css">
</head>
<body>
  <header class="topbar">
    <div>
      <h1>Daily arXiv CV</h1>
      <p id="meta">Loading papers...</p>
    </div>
    <nav>
      <button data-view="latest" class="active">Latest</button>
      <button data-view="favorites">Favorites</button>
    </nav>
  </header>

  <main>
    <section class="controls">
      <input id="search" type="search" placeholder="Search title, keyword, summary">
      <select id="keyword"></select>
    </section>
    <section id="paper-list" class="paper-list"></section>
  </main>

  <template id="paper-template">
    <article class="paper">
      <div class="paper-head">
        <div>
          <a class="title" target="_blank" rel="noreferrer"></a>
          <p class="authors"></p>
        </div>
        <button class="star" title="Toggle local favorite">☆</button>
      </div>
      <div class="tags"></div>
      <dl class="summary">
        <dt>核心贡献</dt>
        <dd class="core"></dd>
        <dt>方法要点</dt>
        <dd class="method"></dd>
      </dl>
      <footer>
        <span class="source"></span>
        <a class="abstract" target="_blank" rel="noreferrer">Abstract</a>
        <a class="html" target="_blank" rel="noreferrer">HTML</a>
        <a class="pdf" target="_blank" rel="noreferrer">PDF</a>
      </footer>
    </article>
  </template>

  <script src="./app-data.js"></script>
  <script src="./app.js"></script>
</body>
</html>
"""


STYLES_CSS = """* {
  box-sizing: border-box;
}

:root {
  color-scheme: light;
  --ink: #191714;
  --muted: #69645f;
  --line: #ddd8cf;
  --paper: #fffdfa;
  --wash: #f4f1eb;
  --accent: #0f766e;
  --accent-ink: #ffffff;
}

body {
  margin: 0;
  background:
    linear-gradient(120deg, rgba(15, 118, 110, 0.08), transparent 34%),
    linear-gradient(180deg, #fbfaf7, var(--wash));
  color: var(--ink);
  font-family: ui-serif, Georgia, "Times New Roman", serif;
}

.topbar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  padding: 28px clamp(18px, 5vw, 56px) 18px;
  border-bottom: 1px solid var(--line);
}

h1 {
  margin: 0;
  font-size: clamp(30px, 5vw, 56px);
  font-weight: 700;
}

p {
  margin: 0;
}

#meta {
  margin-top: 8px;
  color: var(--muted);
  font-family: ui-sans-serif, system-ui, sans-serif;
}

nav {
  display: flex;
  gap: 8px;
}

button,
input,
select {
  font: inherit;
}

button {
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--ink);
  padding: 9px 13px;
  cursor: pointer;
}

button.active {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}

main {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 22px clamp(16px, 4vw, 32px) 56px;
}

.controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 12px;
  margin-bottom: 18px;
}

input,
select {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--ink);
  padding: 12px;
}

.paper-list {
  display: grid;
  gap: 14px;
}

.paper {
  background: rgba(255, 253, 250, 0.86);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}

.paper-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
}

.title {
  color: var(--ink);
  font-size: 21px;
  line-height: 1.25;
  font-weight: 700;
  text-decoration-color: rgba(15, 118, 110, 0.4);
}

.authors {
  margin-top: 7px;
  color: var(--muted);
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 14px;
}

.star {
  width: 42px;
  height: 42px;
  padding: 0;
  font-size: 24px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 14px 0;
}

.tag {
  border: 1px solid var(--line);
  background: #eef7f5;
  color: #115e59;
  padding: 4px 8px;
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 12px;
}

.summary {
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr);
  gap: 9px 14px;
  margin: 0;
}

dt {
  color: var(--accent);
  font-weight: 700;
}

dd {
  margin: 0;
  line-height: 1.55;
}

footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-top: 15px;
  color: var(--muted);
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 13px;
}

footer a {
  color: var(--accent);
}

@media (max-width: 680px) {
  .topbar {
    display: block;
  }

  nav {
    margin-top: 16px;
  }

  .controls {
    grid-template-columns: 1fr;
  }

  .summary {
    grid-template-columns: 1fr;
  }
}
"""


APP_JS = """function readLocalFavorites() {
  try {
    return JSON.parse(localStorage.getItem("arxivFavorites") || "[]");
  } catch {
    return [];
  }
}

const state = {
  papers: [],
  favorites: [],
  view: "latest",
  search: "",
  keyword: "all",
  localFavorites: new Set(readLocalFavorites()),
};

const list = document.querySelector("#paper-list");
const template = document.querySelector("#paper-template");
const search = document.querySelector("#search");
const keyword = document.querySelector("#keyword");
const meta = document.querySelector("#meta");

async function loadJson(path, fallback) {
  const embedded = window.__ARXIV_DATA__ || {};
  if (path.endsWith("/papers.json") && Array.isArray(embedded.papers)) {
    return embedded.papers;
  }
  if (path.endsWith("/favorites.json") && Array.isArray(embedded.favorites)) {
    return embedded.favorites;
  }
  if (path.endsWith("/latest.json") && embedded.latest) {
    return embedded.latest;
  }
  try {
    const response = await fetch(path);
    if (!response.ok) return fallback;
    return await response.json();
  } catch {
    return fallback;
  }
}

function saveLocalFavorites() {
  try {
    localStorage.setItem("arxivFavorites", JSON.stringify([...state.localFavorites]));
  } catch {
  }
}

function allFavoriteIds() {
  return new Set([
    ...state.localFavorites,
    ...state.favorites.map((favorite) => favorite.id),
  ]);
}

function paperText(paper) {
  const summary = paper.summary || {};
  return [
    paper.title,
    (paper.authors || []).join(" "),
    (paper.matched_keywords || []).join(" "),
    summary.core_contribution || "",
    summary.method || "",
  ].join(" ").toLowerCase();
}

function filteredPapers() {
  const favorites = allFavoriteIds();
  const paperById = new Map(state.papers.map((paper) => [paper.id, paper]));
  const favoriteRows = state.favorites.map((favorite) => paperById.get(favorite.id) || {
    id: favorite.id,
    title: favorite.title,
    authors: favorite.authors || [],
    abstract: favorite.abstract || "",
    abstract_url: favorite.abstract_url || favorite.url,
    html_url: favorite.html_url || favorite.url,
    pdf_url: favorite.pdf_url || favorite.url,
    matched_keywords: favorite.tags || [],
    source_used: "favorite",
    summary: {
      core_contribution: favorite.note || "已收藏，暂无本次日报总结。",
      method: "收藏记录保留在 data/favorites.json。",
    },
  });
  const source = state.view === "favorites" ? favoriteRows : state.papers;
  return source.filter((paper) => {
    if (state.view === "favorites" && !favorites.has(paper.id)) return false;
    if (state.keyword !== "all" && !(paper.matched_keywords || []).includes(state.keyword)) return false;
    if (state.search && !paperText(paper).includes(state.search.toLowerCase())) return false;
    return true;
  });
}

function renderKeywordOptions() {
  const keywords = [...new Set(state.papers.flatMap((paper) => paper.matched_keywords || []))].sort();
  keyword.innerHTML = "";
  const all = document.createElement("option");
  all.value = "all";
  all.textContent = "All keywords";
  keyword.append(all);
  for (const item of keywords) {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    keyword.append(option);
  }
}

function render() {
  const favorites = allFavoriteIds();
  const rows = filteredPapers();
  meta.textContent = `${state.papers.length} papers tracked · ${favorites.size} favorites · ${rows.length} shown`;
  list.innerHTML = "";
  for (const paper of rows) {
    const node = template.content.cloneNode(true);
    const title = node.querySelector(".title");
    title.href = paper.abstract_url;
    title.textContent = paper.title;
    node.querySelector(".authors").textContent = (paper.authors || []).slice(0, 8).join(", ");
    const star = node.querySelector(".star");
    star.textContent = favorites.has(paper.id) ? "★" : "☆";
    star.addEventListener("click", () => {
      if (state.localFavorites.has(paper.id)) state.localFavorites.delete(paper.id);
      else state.localFavorites.add(paper.id);
      saveLocalFavorites();
      render();
    });
    const tags = node.querySelector(".tags");
    for (const hit of paper.matched_keywords || []) {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = hit;
      tags.append(tag);
    }
    const summary = paper.summary || {};
    node.querySelector(".core").textContent = summary.core_contribution || "暂无总结。";
    node.querySelector(".method").textContent = summary.method || "暂无总结。";
    node.querySelector(".source").textContent = `source: ${paper.source_used || summary.source_used || "abstract"}`;
    node.querySelector(".abstract").href = paper.abstract_url;
    node.querySelector(".html").href = paper.html_url;
    node.querySelector(".pdf").href = paper.pdf_url;
    list.append(node);
  }
}

document.querySelectorAll("nav button").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    document.querySelectorAll("nav button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    render();
  });
});

search.addEventListener("input", () => {
  state.search = search.value.trim();
  render();
});

keyword.addEventListener("change", () => {
  state.keyword = keyword.value;
  render();
});

async function boot() {
  try {
    state.papers = await loadJson("./data/papers.json", []);
    state.favorites = await loadJson("./data/favorites.json", []);
    renderKeywordOptions();
    render();
  } catch (error) {
    meta.textContent = "Unable to load papers. Rebuild the site data and refresh.";
    console.error(error);
  }
}

boot();
"""


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_data_js(data_dir: Path) -> str:
    payload = {
        "papers": read_json(data_dir / "papers.json", []),
        "favorites": read_json(data_dir / "favorites.json", []),
        "latest": read_json(data_dir / "latest.json", None),
    }
    return (
        "window.__ARXIV_DATA__ = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )


def build_site(data_dir: Path, public_dir: Path) -> None:
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (public_dir / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
    (public_dir / "app-data.js").write_text(build_data_js(data_dir), encoding="utf-8")
    (public_dir / "app.js").write_text(APP_JS, encoding="utf-8")
    target_data = public_dir / "data"
    if target_data.exists():
        shutil.rmtree(target_data)
    if data_dir.exists():
        shutil.copytree(data_dir, target_data)
