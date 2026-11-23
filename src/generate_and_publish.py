#!/usr/bin/env python3
"""Generate a dev article and (optionally) publish to Medium.

Note:
    Medium's legacy Integration Token / Developer API may not be available for new users.
    Even without a Medium token, this script can still generate a daily post and save it to files.

LLM providers (LLM_PROVIDER)
    openai           Any OpenAI-compatible Chat Completions API (default).
                     Use LLM_BASE_URL to point at OpenAI, Azure AI Foundry, Gemini's
                     OpenAI-compatible endpoint, Groq, OpenRouter, a local server, ...
    github_models    RETIRED. GitHub Models was fully retired on 2026-07-30; the host now
                     answers every request with a bare "OK" (HTTP 200, text/plain).
                     Choosing this provider exits immediately with an explanation instead of
                     failing inside the response parser.

Configuration
    LLM_API_KEY  (or OPENAI_API_KEY)   required
    LLM_BASE_URL (or OPENAI_BASE_URL)  optional; defaults to the SDK's OpenAI endpoint
    LLM_MODEL    (or OPENAI_MODEL)     optional; defaults to gpt-4o-mini

Examples:
    python src/generate_and_publish.py --action generate --topic "Asyncio tips" --outdir posts --site_dir site
    python src/generate_and_publish.py --action generate --outdir posts --site_dir site  # auto topic
    python src/generate_and_publish.py --action publish --topic "Asyncio tips" --publish_status draft
    python src/generate_and_publish.py --check-provider
"""
import os
import sys
import argparse
import re
import datetime as _dt
from pathlib import Path
import html as _html
import requests
from dotenv import load_dotenv

import markdown as _md

try:
    from openai import OpenAI

    _OPENAI_V1 = True
except Exception:  # pragma: no cover
    import openai  # type: ignore

    _OPENAI_V1 = False

load_dotenv()

# --------------------------------------------------------------------------------------
# Provider configuration
# --------------------------------------------------------------------------------------

PROVIDER_ALIASES = {
    "": "openai",
    "openai": "openai",
    "openai-compatible": "openai",
    "openai_compatible": "openai",
    "openai-completions": "openai",
    "azure": "openai",
    "azure-openai": "openai",
    "foundry": "openai",
    "gemini": "openai",
    "google": "openai",
    "groq": "openai",
    "openrouter": "openai",
    "ollama": "openai",
    "github": "github_models",
    "github_models": "github_models",
    "github-models": "github_models",
    "gh": "github_models",
}

GITHUB_MODELS_RETIRED_ON = "2026-07-30"
RETIRED_MODEL_HOSTS = ("models.github.ai", "models.inference.ai.azure.com")

GITHUB_MODELS_RETIREMENT_MESSAGE = (
    "GitHub Models was fully retired on "
    f"{GITHUB_MODELS_RETIRED_ON}, so https://models.github.ai/inference no longer serves "
    "inference to any customer: it now answers every request with HTTP 200, "
    "content-type text/plain and the body 'OK'. That is the text this job used to report as "
    "'Unexpected response ... OK'.\n"
    "Pick another provider and set it in the repository secrets/variables:\n"
    "  LLM_PROVIDER=openai (default)\n"
    "  LLM_API_KEY=<key>            # e.g. OpenAI, Azure AI Foundry, Gemini, Groq\n"
    "  LLM_BASE_URL=<optional>      # only for non-OpenAI OpenAI-compatible endpoints\n"
    "  LLM_MODEL=<optional>         # defaults to gpt-4o-mini\n"
    "GitHub's own replacement for workflow inference is actions/ai-inference (Copilot); "
    "Microsoft points GitHub Models users at Azure AI Foundry."
)


class ProviderError(RuntimeError):
    """Base class for provider configuration/call problems."""


class ProviderNotConfigured(ProviderError):
    """No usable credential is set, so generation cannot run."""


class ProviderRetired(ProviderError):
    """The configured provider no longer exists upstream."""


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return ""


def resolve_provider() -> str:
    raw = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    provider = PROVIDER_ALIASES.get(raw)
    if provider is None:
        provider = "openai" if raw.startswith("openai") else raw
    if provider == "github_models":
        raise ProviderRetired(GITHUB_MODELS_RETIREMENT_MESSAGE)
    if provider != "openai":
        raise ProviderError(
            f"Unknown LLM_PROVIDER {raw!r}. Supported: openai (any OpenAI-compatible API), "
            "or github_models (retired)."
        )
    base_url = _env("LLM_BASE_URL", "OPENAI_BASE_URL", "GITHUB_MODELS_BASE_URL")
    if any(host in base_url for host in RETIRED_MODEL_HOSTS):
        raise ProviderRetired(GITHUB_MODELS_RETIREMENT_MESSAGE)
    return provider


def api_key() -> str:
    return _env("LLM_API_KEY", "OPENAI_API_KEY")


def base_url() -> str:
    return _env("LLM_BASE_URL", "OPENAI_BASE_URL", "GITHUB_MODELS_BASE_URL")


def model_id() -> str:
    return _env("LLM_MODEL", "OPENAI_MODEL") or "gpt-4o-mini"


def missing_configuration() -> str:
    """Return a human-readable reason generation cannot run, or an empty string."""
    if resolve_provider() != "openai":  # pragma: no cover - resolve_provider raises first
        return "No usable LLM provider is configured."
    if not api_key():
        return (
            "No LLM credential is configured (LLM_API_KEY or OPENAI_API_KEY is empty). "
            "GitHub Models, the previous provider, was retired on "
            f"{GITHUB_MODELS_RETIRED_ON}, so a new provider key is required."
        )
    return ""


MEDIUM_TOKEN = os.getenv("MEDIUM_INTEGRATION_TOKEN")
DEFAULT_PUBLISH_STATUS = os.getenv("DEFAULT_PUBLISH_STATUS", "draft")

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not _OPENAI_V1:  # pragma: no cover
        raise ProviderError(
            "openai>=1 is required (the installed 'openai' package has no OpenAI client). "
            "Run: python -m pip install -r requirements.txt"
        )
    kwargs = {"api_key": api_key(), "max_retries": 3, "timeout": 300.0}
    url = base_url()
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        kwargs["base_url"] = url
    _client = OpenAI(**kwargs)
    return _client


def _body_text(payload) -> str:
    if payload is None:
        return ""
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode("utf-8", "replace")
    if isinstance(payload, str):
        return payload
    return repr(payload)


def _retirement_hint(body: str) -> str:
    if body.strip().lower() in ("ok", "ok.", "healthy"):
        return (
            "\nA bare 'OK' body is what the retired GitHub Models host (models.github.ai) "
            f"returns for every request since {GITHUB_MODELS_RETIRED_ON}. "
            "If LLM_BASE_URL still points there, switch providers."
        )
    return ""


def _completion_text(resp) -> str:
    """Return the assistant text, failing loudly when the endpoint answers with something
    other than a chat completion (dead endpoint, wrong URL, blocked egress, proxy or
    gateway placeholder).
    """
    choices = getattr(resp, "choices", None)
    if not choices:
        body = _body_text(resp)
        raise RuntimeError(
            "The LLM endpoint answered without a chat completion "
            f"(model {model_id()}, base_url {base_url() or 'https://api.openai.com/v1'}): "
            f"{body[:300]!r}.{_retirement_hint(body)}"
        )
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(choices[0], dict):  # pragma: no cover - defensive for dict-shaped payloads
        content = (choices[0].get("message") or {}).get("content")
    text = (content or "").strip()
    if not text:
        raise RuntimeError(
            "The LLM endpoint returned an empty completion "
            f"(model {model_id()}). Check the model name and the provider quota."
        )
    return text


def _describe_failure(exc: Exception) -> str:
    parts = [f"{type(exc).__name__}: {exc}"]
    status = getattr(exc, "status_code", None)
    if status:
        parts.append(f"HTTP status: {status}")
    response = getattr(exc, "response", None)
    if response is not None:
        body = _body_text(getattr(response, "text", ""))
        if body:
            parts.append(f"response body: {body[:300]!r}{_retirement_hint(body)}")
    return "LLM request failed for model " + model_id() + " at " + (
        base_url() or "https://api.openai.com/v1"
    ) + "\n" + "\n".join(parts)


def _in_actions() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true"


def _annotate(level: str, message: str) -> None:
    if _in_actions():
        first_line = message.strip().splitlines()[0]
        print(f"::{level}::{first_line}")
    print(message, file=sys.stderr if level in ("error", "warning") else sys.stdout)


def _write_step_summary(message: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        Path(path).write_text(f"### Daily Medium draft\n\n{message}\n", encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------------------


def generate_article(topic: str, audience: str = "senior software engineers", length: str = "~1400-1800 words") -> dict:
    system = (
        "You are a staff-level software engineer and technical writer. "
        "Write a Medium-ready article IN ENGLISH about the given topic, aimed at readers with ~10+ years of experience. "
        "Assume the reader already knows the basics; do not explain fundamentals. "
        "Avoid generic advice and motivational filler. Every section must include actionable, technical details. "
        "\n\n"
        "Hard requirements:\n"
        "- Provide a strong, specific thesis (not a list of tips).\n"
        "- Include at least 2 code blocks that demonstrate non-trivial implementation details.\n"
        "- Include at least 1 'Failure modes & debugging' section with concrete symptoms and diagnoses.\n"
        "- Include at least 1 'Trade-offs' section with when NOT to use the approach.\n"
        "- Include at least 1 'Performance & cost' section (latency, throughput, memory, or cloud cost), using clearly-labeled illustrative numbers if needed.\n"
        "- Include at least 1 'Observability' section: metrics, logs, traces, and what to alert on.\n"
        "- End with a short checklist that an experienced engineer can apply tomorrow.\n"
        "\n\n"
        "Code requirements (critical):\n"
        "- Code must be properly indented and copy/paste runnable.\n"
        "- Use ONLY straight ASCII quotes in code: ' and \". Never use smart quotes (e.g. “ ” ‘ ’).\n"
        "- Use fenced code blocks with language tags, e.g. ```python or ```sql.\n"
        "- Do not include pseudo-code inside code fences; if you need pseudo-code, write it outside fences.\n"
        "\n\n"
        "Format requirements:\n"
        "- Start with: '# <Title>' then a one-sentence subtitle in italics.\n"
        "- Use headings with clear section titles.\n"
        "- Keep it dense and technical.\n"
        "- Return ONLY the article in Markdown."
    )

    prompt = (
        f"Topic: {topic}\n"
        f"Audience: {audience}\n"
        f"Target length: {length}\n\n"
        "Write with these additional constraints:\n"
        "- Prefer a single focused scenario (one system / one workload) and go deep.\n"
        "- Show the reasoning chain explicitly (constraints -> design -> implementation -> validation).\n"
        "- If you make assumptions, state them. Do not invent citations or claim you ran benchmarks.\n"
        "- Use examples that would survive code review in a production codebase.\n"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=model_id(),
            messages=messages,
            temperature=0.7,
            max_tokens=1400,
        )
    except ProviderError:  # pragma: no cover - configuration problems are raised earlier
        raise
    except Exception as exc:
        raise RuntimeError(_describe_failure(exc)) from exc

    text = _completion_text(resp)

    # A simple split: consider first heading as title if present
    return {"markdown": normalize_markdown_for_medium(text)}


def normalize_markdown_for_medium(markdown_text: str) -> str:
    """Best-effort normalization for copy/paste into Medium.

    Medium's editor can behave poorly with smart quotes and some unicode punctuation inside code fences.
    This function only normalizes inside fenced code blocks and leaves prose untouched.
    """

    replacements = {
        "\u2018": "'",  # ‘
        "\u2019": "'",  # ’
        "\u201C": '"',  # “
        "\u201D": '"',  # ”
        "\u2013": "-",  # –
        "\u2014": "-",  # —
        "\u00A0": " ",  # nbsp
    }

    def _replace_chars(s: str) -> str:
        for old, new in replacements.items():
            s = s.replace(old, new)
        return s

    lines = markdown_text.splitlines()
    out = []
    in_fence = False
    fence = "```"

    for line in lines:
        if line.strip().startswith(fence):
            in_fence = not in_fence
            out.append(line)
            continue

        out.append(_replace_chars(line) if in_fence else line)

    return "\n".join(out).strip() + "\n"


def get_medium_user_id(token: str) -> str:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.get("https://api.medium.com/v1/me", headers=headers)
    r.raise_for_status()
    return r.json()["data"]["id"]


def publish_to_medium(token: str, user_id: str, title: str, content_md: str, publish_status: str = "draft", tags=None):
    if tags is None:
        tags = []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    body = {
        "title": title,
        "contentFormat": "markdown",
        "content": content_md,
        "publishStatus": publish_status,
        "tags": tags,
    }
    url = f"https://api.medium.com/v1/users/{user_id}/posts"
    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()
    return r.json()


def extract_title(markdown: str) -> str:
    # Find first H1 or H2
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    # fallback: first line
    return markdown.splitlines()[0][:80]


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80] or "post"


def save_markdown(outdir: str, title: str, markdown: str) -> str:
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().isoformat()
    slug = _slugify(title)
    file_path = out_path / f"{today}-{slug}.md"
    if not markdown.lstrip().startswith("# "):
        markdown = f"# {title}\n\n" + markdown
    file_path.write_text(markdown, encoding="utf-8")
    return str(file_path)


def render_html(title: str, markdown_text: str) -> str:
    # To make copy/paste & import easier, remove the first H1 from the Markdown
    # and render a single <h1> in the HTML template.
    md_text = markdown_text.lstrip("\ufeff")
    lines = md_text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].startswith("# "):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        md_text = "\n".join(lines[i:])

    body = _md.markdown(
        md_text,
        extensions=["fenced_code", "tables"],
        output_format="html5",
    )
    safe_title = _html.escape(title)
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>\n"
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        "    /* Minimal styles for copy/paste/import */\n"
        "    body { margin: 0; font: 16px/1.7 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color: #111; }\n"
        "    main { max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }\n"
        "    article > h1 { margin: 0 0 16px; line-height: 1.2; }\n"
        "    pre { overflow: auto; padding: 12px; background: #f6f8fa; }\n"
        "    code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.95em; }\n"
        "    table { border-collapse: collapse; width: 100%; }\n"
        "    th, td { border: 1px solid #ddd; padding: 6px 8px; }\n"
        "    a { word-break: break-word; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <article>\n"
        f"      <h1>{safe_title}</h1>\n"
        f"      {body}\n"
        "    </article>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def save_html(site_dir: str, md_file_path: str, title: str, markdown_text: str) -> str:
    base = Path(md_file_path).stem
    out_dir = Path(site_dir) / "posts"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{base}.html"
    html_text = render_html(title, markdown_text)
    html_path.write_text(html_text, encoding="utf-8")
    return str(html_path)


def build_site_index(posts_dir: str, site_dir: str, limit: int = 60) -> str:
    posts_path = Path(posts_dir)
    site_path = Path(site_dir)
    site_path.mkdir(parents=True, exist_ok=True)
    items = []
    for md_path in sorted(posts_path.glob("*.md"), reverse=True):
        md_text = md_path.read_text(encoding="utf-8")
        title = extract_title(md_text)
        base = md_path.stem
        items.append((md_path.name, title, f"posts/{base}.html"))
    items = items[:limit]

    li = "\n".join(
        f"<li><a href=\"{_html.escape(href)}\">{_html.escape(title)}</a> <small>({fname})</small></li>"
        for fname, title, href in items
    )

    index_html = (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>\n"
        "  <title>Daily Dev Posts</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light dark; }\n"
        "    body { margin: 0; font: 16px/1.6 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }\n"
        "    main { max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }\n"
        "    ul { padding-left: 18px; }\n"
        "    small { opacity: 0.7; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <h1>Daily Dev Posts</h1>\n"
        "    <p>Auto-generated posts. Copy/paste into Medium, or use Medium import if available.</p>\n"
        "    <ul>\n"
        f"{li}\n"
        "    </ul>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )

    out = site_path / "index.html"
    out.write_text(index_html, encoding="utf-8")
    return str(out)


def default_topic() -> str:
    today = _dt.date.today()
    topics = [
        "Chunking vs. Late Chunking vs. Contextual Retrieval in Production RAG",
        "Hybrid Search with BM25, Dense Embeddings, and Reciprocal Rank Fusion (RRF)",
        "KV Cache Management & PagedAttention: Reducing Memory Footprint in High-Throughput LLM Serving",
        "Speculative Decoding in Production: Throughput vs. Latency Trade-offs in Self-Hosted LLMs",
        "Building Reliable LLM Agents: Why State Machines Beat Autonomous ReAct Loops",
        "Structured Outputs in Production: Eliminating Schema Drift with Pydantic, Instructor, and BAML",
        "Semantic Caching for LLM APIs: Cache Invalidation, Embedding Distance, and Cost Reduction",
        "Smart Prompt Routing & Model Cascades: Cutting Token Costs 80% with Smaller Specialist Models",
        "Production Vector Search at Scale: HNSW vs. IVF-PQ Trade-offs and Index Tuning",
        "Fine-tuning vs. In-Context Learning vs. RAG: Real-World Cost, Latency, and Maintenance Matrix",
        "LLM-as-a-Judge in CI/CD: Building Automated Evaluation Pipelines That Correlate with Human Preference",
        "Local LLM Inference Architecture: Comparing vLLM, Ollama, and llama.cpp for Production Edge Workloads",
    ]

    topic = topics[today.toordinal() % len(topics)]
    return f"{topic} ({today.isoformat()})"


def provider_report() -> dict:
    report = {
        "provider": "openai",
        "base_url": base_url() or "https://api.openai.com/v1",
        "model": model_id(),
        "api_key": "set" if api_key() else "missing",
        "ready": False,
        "reason": "",
    }
    try:
        resolve_provider()
    except ProviderRetired as exc:
        report.update(provider="github_models (retired)", ready=False, reason=str(exc))
        return report
    except ProviderError as exc:
        report.update(ready=False, reason=str(exc))
        return report
    reason = missing_configuration()
    report["ready"] = not reason
    report["reason"] = reason
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--action", choices=["generate", "publish", "generate_and_publish"], default="generate")
    p.add_argument("--topic", required=False)
    p.add_argument("--outdir", default="posts")
    p.add_argument("--site_dir", default="site")
    p.add_argument("--publish_status", default=DEFAULT_PUBLISH_STATUS)
    p.add_argument("--tags", default=None)
    p.add_argument(
        "--check-provider",
        action="store_true",
        help="Print the resolved provider configuration and exit (0 ready, 3 not configured, 4 provider retired).",
    )
    p.add_argument(
        "--allow-skip",
        action="store_true",
        help="Exit successfully with a warning when no LLM credential is configured (scheduled runs).",
    )
    args = p.parse_args()

    if args.check_provider:
        report = provider_report()
        for key, value in report.items():
            print(f"{key}: {value}")
        return 0 if report["ready"] else 4 if report["provider"].startswith("github_models") else 3

    try:
        reason = missing_configuration()
    except ProviderRetired as exc:
        _annotate("error", str(exc))
        return 4
    except ProviderError as exc:
        _annotate("error", str(exc))
        return 3

    if reason:
        if args.allow_skip:
            _annotate("warning", f"Skipping today's post: {reason}")
            _write_step_summary(
                "**Skipped: no LLM provider credential.**\n\n"
                f"{reason}\n\n"
                "Add `LLM_API_KEY` (or `OPENAI_API_KEY`) as a repository secret and, for "
                "non-OpenAI endpoints, `LLM_BASE_URL` / `LLM_MODEL` as repository variables."
            )
            print("No post generated (provider not configured).")
            return 0
        _annotate("error", reason)
        return 3

    topic = args.topic or default_topic()

    try:
        art = generate_article(topic)
    except ProviderRetired as exc:
        _annotate("error", str(exc))
        return 4
    except ProviderError as exc:
        _annotate("error", str(exc))
        return 3
    except RuntimeError as exc:
        _annotate("error", str(exc))
        return 1

    md = art["markdown"]

    title = extract_title(md)
    saved = save_markdown(args.outdir, title, md)
    html_saved = save_html(args.site_dir, saved, title, md)
    index_saved = build_site_index(args.outdir, args.site_dir)

    if args.action == "generate":
        print(saved)
        print(html_saved)
        print(index_saved)
        return 0

    # publish or generate_and_publish
    if not MEDIUM_TOKEN:
        raise RuntimeError(
            "MEDIUM_INTEGRATION_TOKEN not set.\n"
            "- If Medium Integration Tokens are not available for your account, automated publishing via API is not possible.\n"
            "- Use the generated files (posts/*.md or site/posts/*.html) and paste/import into Medium."
        )
    user_id = get_medium_user_id(MEDIUM_TOKEN)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    resp = publish_to_medium(MEDIUM_TOKEN, user_id, title, md, publish_status=args.publish_status, tags=tags)
    print("Published:", resp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
