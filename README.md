# daily_arxiv_paper

Daily arXiv CV tracker. It fetches papers by keyword, summarizes them with an API when available, writes the latest filtered result as JSON, and builds a public static site for GitHub Pages. Slack is no longer the primary output path.

## Architecture

```text
GitHub Actions cron
  -> python -m daily_arxiv_paper run-daily
  -> fetch recent arXiv papers
  -> match configured keywords
  -> read source text: HTML, then abstract, then PDF fallback
  -> summarize with OpenAI if OPENAI_API_KEY is configured
  -> overwrite data/papers.json and data/latest.json
  -> build public/ for GitHub Pages
```

The important persisted files are:

- `data/papers.json`: latest filtered paper list, overwritten each run.
- `data/latest.json`: metadata and paper list for the latest run.
- `data/favorites.json`: curated favorites for the public site.
- `public/`: generated GitHub Pages site.

## Setup

Adjust `config.json`:

- `category`: arXiv category, for example `cs.CV`.
- `keywords`: case-insensitive keyword filters. Current default: `video`, `retrieval`, `3d`, `agent`, `representation`, `instance`, `multimodal`, `diffusion`.
- `max_results`: maximum papers fetched from arXiv per run.
- `fetch_window_hours`: broad fetch window used to avoid missing papers after outages.
- `daily_window_hours`: window shown as current daily results.
- `openai_model`: model used for summaries.
- `summarize_max_papers`: maximum new papers summarized per run.

Optional `.env`:

```bash
OPENAI_API_KEY=your_openai_api_key
```

If `OPENAI_API_KEY` is missing, the pipeline still publishes papers with a fallback abstract-based summary.

## Commands

Run the full daily pipeline:

```bash
python3 -m daily_arxiv_paper run-daily
```

Print machine-readable output:

```bash
python3 -m daily_arxiv_paper run-daily --json
```

Fetch matching papers without writing data:

```bash
python3 -m daily_arxiv_paper fetch --json
```

Rebuild the static site from existing data:

```bash
python3 -m daily_arxiv_paper build-site
```

Manage favorites:

```bash
python3 -m daily_arxiv_paper favorite add 2401.01234 --tag retrieval --note "Read later"
python3 -m daily_arxiv_paper favorite list
python3 -m daily_arxiv_paper favorite search retrieval
python3 -m daily_arxiv_paper favorite remove 2401.01234
```

Legacy aliases still work:

```bash
python3 -m daily_arxiv_paper star 2401.01234
python3 -m daily_arxiv_paper list
python3 -m daily_arxiv_paper search retrieval
```

## GitHub Pages

The workflow in `.github/workflows/daily_arxiv.yml` runs every day at 09:00 China Standard Time, commits changed `data/` and `public/` files, and deploys `public/` through GitHub Pages. Daily result files are overwritten instead of accumulated; only `data/favorites.json` is intended to grow over time.

In the GitHub repository:

1. Add `OPENAI_API_KEY` as an Actions secret if you want model summaries.
2. Enable Pages with "GitHub Actions" as the source.
3. Run the workflow manually once from the Actions tab to verify deployment.
