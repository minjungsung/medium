#!/usr/bin/env python3
"""Generate a dev article and (optionally) publish to Medium.

Important:
    Medium의 공식 Developer API(Integration Token)가 더 이상 발급되지 않는 계정/환경이 있습니다.
    그런 경우에도 이 스크립트는 매일 글을 자동 생성해 파일로 저장할 수 있습니다.

Examples:
    python src/generate_and_publish.py --action generate --topic "Asyncio 팁" --outdir posts
    python src/generate_and_publish.py --action generate  --outdir posts   # topic 미지정 시 날짜 기반 토픽
    python src/generate_and_publish.py --action publish --topic "Asyncio 팁" --publish_status draft
"""
import os
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_MODELS_TOKEN")
GITHUB_MODELS_BASE_URL = (os.getenv("GITHUB_MODELS_BASE_URL") or "https://models.inference.ai.azure.com").strip()
if GITHUB_MODELS_BASE_URL and not (GITHUB_MODELS_BASE_URL.startswith("http://") or GITHUB_MODELS_BASE_URL.startswith("https://")):
    GITHUB_MODELS_BASE_URL = "https://" + GITHUB_MODELS_BASE_URL
MEDIUM_TOKEN = os.getenv("MEDIUM_INTEGRATION_TOKEN")
DEFAULT_PUBLISH_STATUS = os.getenv("DEFAULT_PUBLISH_STATUS", "draft")

def _make_client():
    if not _OPENAI_V1:
        return None

    if LLM_PROVIDER in ("github", "github_models", "gh", "github-models"):
        if not GITHUB_TOKEN:
            raise RuntimeError(
                "LLM_PROVIDER=github_models 인데 GITHUB_TOKEN(또는 GH_MODELS_TOKEN)이 없습니다.\n"
                "- GitHub Models 접근 권한이 있는 토큰을 환경변수로 설정하세요."
            )
        return OpenAI(api_key=GITHUB_TOKEN, base_url=GITHUB_MODELS_BASE_URL)

    # default: OpenAI
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in env")
    return OpenAI(api_key=OPENAI_API_KEY)


if _OPENAI_V1:
    _client = _make_client()
else:  # pragma: no cover
    openai.api_key = OPENAI_API_KEY  # type: ignore


def generate_article(topic: str, audience: str = "developers", length: str = "~800 words") -> dict:
    system = (
        "You are an expert technical writer. Produce a Medium-ready article in Korean about the given topic. "
        "Write a catchy title, a short subtitle (1 sentence), and the article body. Use headings, code blocks if needed, and a concise conclusion. "
        "Return only the article in markdown format."
    )

    prompt = f"Topic: {topic}\nAudience: {audience}\nLength: {length}\nPlease produce: Title, Subtitle, Body (markdown)."

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    if _OPENAI_V1:
        resp = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1400,
        )
        text = resp.choices[0].message.content.strip() if resp.choices[0].message.content else ""
    else:  # pragma: no cover
        resp = openai.ChatCompletion.create(  # type: ignore
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1400,
        )
        text = resp["choices"][0]["message"]["content"].strip()

    # A simple split: consider first heading as title if present
    return {"markdown": text}


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
    text = re.sub(r"[^a-z0-9가-힣\s-]", "", text)
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
    # Medium에 붙여넣기/Import 할 때 제목이 중복되지 않도록,
    # 본문 변환에서는 선두 H1을 제거하고 HTML 템플릿에서 제목을 한 번만 렌더링합니다.
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
        "<html lang=\"ko\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>\n"
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        "    /* Copy/Paste/Import 친화적인 최소 스타일 */\n"
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
        "<html lang=\"ko\">\n"
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
        "    <p>자동 생성된 글 목록입니다. Medium에 올릴 때는 본문을 복사/붙여넣기 하거나 Import에 활용하세요.</p>\n"
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
    today = _dt.date.today().isoformat()
    return f"오늘의 개발 팁 ({today})"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--action", choices=["generate", "publish", "generate_and_publish"], default="generate")
    p.add_argument("--topic", required=False)
    p.add_argument("--outdir", default="posts")
    p.add_argument("--site_dir", default="site")
    p.add_argument("--publish_status", default=DEFAULT_PUBLISH_STATUS)
    p.add_argument("--tags", default=None)
    args = p.parse_args()

    topic = args.topic or default_topic()

    art = generate_article(topic)
    md = art["markdown"]

    title = extract_title(md)
    saved = save_markdown(args.outdir, title, md)
    html_saved = save_html(args.site_dir, saved, title, md)
    index_saved = build_site_index(args.outdir, args.site_dir)

    if args.action == "generate":
        print(saved)
        print(html_saved)
        print(index_saved)
        return

    # publish or generate_and_publish
    if not MEDIUM_TOKEN:
        raise RuntimeError(
            "MEDIUM_INTEGRATION_TOKEN not set.\n"
            "- Medium에서 Integration Token 발급 UI가 사라진 경우, API로 자동 업로드가 불가합니다.\n"
            "- 대신 생성된 파일(posts/*.md)을 Medium 에디터에 붙여넣거나 'Import story'로 가져오는 방식을 사용하세요."
        )
    user_id = get_medium_user_id(MEDIUM_TOKEN)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    resp = publish_to_medium(MEDIUM_TOKEN, user_id, title, md, publish_status=args.publish_status, tags=tags)
    print("Published:", resp)


if __name__ == "__main__":
    main()
