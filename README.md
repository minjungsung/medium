# GPT Copilot로 매일 Medium 글 연재하기

이 저장소는 GPT(또는 Copilot 스타일 LLM)를 사용해 매일 개발 관련 Medium 글을 자동 생성하고 업로드할 수 있는 간단한 파이썬 스크립트를 제공합니다.

주요 기능
- 로컬에서 토픽을 기반으로 LLM에 아티클 생성 요청
- (가능한 경우) Medium Integration Token을 사용해 글을 업로드(초기에는 draft)
- cron 또는 GitHub Actions로 일일 자동 실행 가능

빠른 시작
1. `.env`를 만들고 다음 값을 설정하세요:

- `LLM_PROVIDER` — `openai` 또는 `github_models`
- `OPENAI_MODEL` — 사용할 모델 (예: gpt-4o-mini 또는 환경 기본)
- `OPENAI_API_KEY` — (LLM_PROVIDER=openai일 때) OpenAI 호환 키
- `GITHUB_TOKEN` — (LLM_PROVIDER=github_models일 때) GitHub Models 접근 토큰
- `MEDIUM_INTEGRATION_TOKEN` — Medium Integration Token (레거시: 계정에 따라 신규 발급이 불가할 수 있음)

2. 의존성 설치:
```bash
python -m pip install -r requirements.txt
```

3. 예시 실행 (즉시 생성 후 로컬 출력):
```bash
python src/generate_and_publish.py --action generate --topic "Python 성능 최적화 팁" --outdir posts --site_dir site
```

4. 예시로 생성 후 Medium에 업로드:
```bash
python src/generate_and_publish.py --action publish --topic "컨커런시와 asyncio 최적화" --publish_status draft
```

Medium Integration Token이 없을 때
- Medium 설정에서 Integration Token 생성 메뉴가 없다면, 공식 API로 자동 업로드는 사실상 불가능합니다.
- 대신 `--action generate`로 매일 글을 생성해 `posts/`에 저장하고, 동시에 HTML을 `site/`에 생성합니다.
- GitHub Pages로 `site/`를 배포하면, 웹에서 글을 확인하고 Medium에 복사/붙여넣기 또는 Import에 활용하기가 편합니다. (HTML은 제목 중복을 피하도록 비교적 “깔끔한” 형태로 생성됩니다.)

GitHub Pages 설정
- 이 repo는 `site/` 폴더를 Pages로 배포하도록 워크플로가 포함되어 있습니다: `.github/workflows/deploy_pages.yml`.
- GitHub에서 Settings → Pages → Build and deployment를 **GitHub Actions**로 설정하세요.

Medium에 올리는 방법(토큰 없을 때)
- `site/index.html`에 최신 글 목록이 생성됩니다.
- 원하는 글의 HTML 페이지를 열고 본문을 복사해 Medium 에디터에 붙여넣거나, Medium의 Import 기능이 있으면 그 URL을 활용하세요.

스케줄링
- 시스템 `cron`에 위 명령을 등록하거나 `.github/workflows/daily_publish.yml`을 사용해 GitHub Actions에서 스케줄 실행할 수 있습니다. README 내 예시를 참조하세요.

보안
- API 키와 토큰은 절대 공개 저장소에 저장하지 마세요. `.env` 사용을 권장합니다.

"GitHub Copilot로" 생성하고 싶을 때
- Copilot Chat 자체를 외부 스크립트에서 호출하는 공식 공개 API는 일반적으로 제공되지 않습니다.
- 대신 GitHub가 제공하는 OpenAI-호환 "GitHub Models" 엔드포인트를 사용하면 `GITHUB_TOKEN`으로 글 생성 자동화를 구성할 수 있습니다.

더 원하는 기능 (예): 태그 자동 생성, SEO 제목/요약 자동 생성, 자동 공개 게시 등 — 원하시면 추가합니다.
