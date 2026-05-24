# Daily Medium Dev Posts (English)

This repo generates one developer-focused post per day (in English), saves it as Markdown + HTML, and optionally publishes to Medium (only if you have a legacy Medium Integration Token).

## What you get

- Generate a Medium-ready article with an LLM
- Save to `posts/` as Markdown
- Render to `site/` as static HTML + `site/index.html`
- Automate via GitHub Actions (daily) or local cron

## Quick start (local)

1) Create `.env` (see `.env.example`) and set at least:

- `LLM_PROVIDER=github_models` (recommended)
- `GITHUB_TOKEN=...` (or `GH_MODELS_TOKEN=...`)
- `OPENAI_MODEL=...`

2) Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

3) Generate today's post:

```bash
python3 src/generate_and_publish.py --action generate --outdir posts --site_dir site
```

It prints the generated file paths (Markdown, HTML, and `site/index.html`).

## GitHub Actions (daily)

The daily generator workflow is at `.github/workflows/daily_generate.yml`.

Add these repo secrets:

- `GH_MODELS_TOKEN` (required)
- `OPENAI_MODEL` (optional; defaults to `gpt-4o-mini`)

Then run the workflow manually once from the Actions tab to verify it works.

## GitHub Pages (optional)

This repo includes a Pages deploy workflow: `.github/workflows/deploy_pages.yml`.

In GitHub:

1) Settings → Pages
2) Build and deployment → select **GitHub Actions**

After each push to `main`, `site/` is deployed.

## Medium publishing (token may be unavailable)

Medium has a legacy Integration Token / Developer API, but many accounts can no longer create new tokens.

- If you **do not** have `MEDIUM_INTEGRATION_TOKEN`, use `--action generate` and paste/import from the generated files.
- If you **do** have a token, you can try:

```bash
python3 src/generate_and_publish.py --action publish --topic "Asyncio tips" --publish_status draft
```

## Formatting in Medium (Markdown vs HTML)

Medium's editor is not a full Markdown editor. Depending on how you paste, code indentation and quotes can get mangled.

Recommended options:

- Best: deploy `site/` to GitHub Pages and use the generated HTML (`site/posts/*.html`) as your source for Medium import/copy.
- If you paste Markdown from `posts/*.md`, make sure code blocks stay inside fenced code blocks (```python) and avoid smart quotes.

This repo also normalizes smart quotes/dashes inside fenced code blocks to reduce copy/paste issues.

## English-only output

The generator is configured to produce articles in **English only**.

## Security

Never commit secrets. `.gitignore` already excludes `.env`.
