# Daily Medium Dev Posts (English)

This repo generates one developer-focused post per day (in English), saves it as Markdown + HTML, and optionally publishes to Medium (only if you have a legacy Medium Integration Token).

## What you get

- Generate a Medium-ready article with an LLM
- Save to `posts/` as Markdown
- Render to `site/` as static HTML + `site/index.html`
- Automate via GitHub Actions (daily) or local cron

## Quick start (local)

1) Create `.env` (see `.env.example`) and set at least:

- `LLM_PROVIDER=openai` (any OpenAI-compatible API; this is the default)
- `LLM_API_KEY=...` (or `OPENAI_API_KEY=...`)
- `LLM_BASE_URL=...` (only for non-OpenAI endpoints, e.g. Azure AI Foundry, Gemini, Groq)
- `LLM_MODEL=gpt-4o-mini` (optional, this is the default)

> **GitHub Models is gone.** GitHub Models was fully retired on 2026-07-30; the playground,
> model catalog, inference API and BYOK are no longer available to any customer, and
> `https://models.github.ai/inference` now answers every request with `HTTP 200`, `text/plain`,
> body `OK`. That placeholder answer is why this repo's daily job reported
> `Unexpected response ... 'OK'` for months. Set `LLM_PROVIDER=github_models` and the script now
> stops immediately with that explanation instead of calling the dead endpoint.

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

Add these repository settings (Settings → Secrets and variables → Actions):

- Secret `LLM_API_KEY` (or `OPENAI_API_KEY`) — the model provider key. **Required.**
- Variable `LLM_PROVIDER` — optional, defaults to `openai`.
- Variable `LLM_BASE_URL` — optional, for an OpenAI-compatible endpoint other than OpenAI.
- Variable `LLM_MODEL` — optional, defaults to `gpt-4o-mini`.

Check the configuration any time without spending a token:

```bash
LLM_API_KEY=... python3 src/generate_and_publish.py --check-provider
```

It prints `provider`, `base_url`, `model`, `api_key` and `ready`, and exits `0` when ready,
`3` when no credential is set, `4` when the provider is retired.

While no credential is configured the scheduled run does **not** fail: it prints a warning
(`Skipping today's post: no LLM credential ...`), writes the reason to the job summary, and ends
successfully, so the daily red run stops without hiding the reason. Once `LLM_API_KEY` is set the
same job starts producing a post per day again. A *configured* provider that errors still fails
the run loudly.

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

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests run the real script against a local OpenAI-compatible stub: a normal completion must
write `posts/*.md`, `site/posts/*.html` and `site/index.html`; the retired host's `OK` body must
be reported as the retired provider; a missing credential must skip with `--allow-skip` and fail
(exit 3) without it.
