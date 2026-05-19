function readLocalFavorites() {
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
