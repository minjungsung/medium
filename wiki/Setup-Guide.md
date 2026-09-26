# Setup Guide

> 로컬 실행, GitHub Actions 설정, 환경변수 가이드

## 사전 요구사항

| 도구 | 최소 버전 | 용도 |
|------|----------|------|
| Python | 3.10+ | 런타임 |
| pip | 23.0+ | 패키지 관리 |
| Git | 2.30+ | 소스 관리 |
| OpenAI API Key | - | 포스트 생성 |

## 로컬 실행

### 1단계: 리포지토리 클론

```bash
git clone https://github.com/minjungsung/medium.git
cd medium
```

### 2단계: Python 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 3단계: 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 또는 직접 export
export OPENAI_API_KEY="sk-your-api-key-here"
```

### 4단계: 포스트 생성 및 빌드

```bash
# 새 포스트 생성
python scripts/generate.py

# 생성된 Markdown 확인
ls posts/

# HTML로 변환 및 사이트 빌드
python scripts/publish.py

# 로컬 미리보기
python -m http.server 8080 --directory site/
# 브라우저에서 http://localhost:8080 접속
```

## GitHub Actions 설정

### Repository Secrets 설정

GitHub 리포지토리에서 다음 Secrets을 설정해야 합니다:

1. 리포지토리 Settings > Secrets and variables > Actions
2. New repository secret 클릭

| Secret 이름 | 설명 | 필수 |
|-------------|------|------|
| `OPENAI_API_KEY` | OpenAI API 키 | Yes |
| `GH_PAT` | GitHub Personal Access Token (workflow trigger용) | 선택 |

### GitHub Pages 활성화

1. 리포지토리 Settings > Pages
2. Source: GitHub Actions 선택
3. 또는 Branch: `gh-pages` / root 선택

### 워크플로우 권한 설정

1. Settings > Actions > General
2. Workflow permissions: Read and write permissions 선택
3. Allow GitHub Actions to create and approve pull requests 체크

### 워크플로우 수동 실행

```bash
# GitHub CLI로 워크플로우 수동 실행
gh workflow run daily_generate.yml
gh workflow run daily_publish.yml

# 워크플로우 실행 상태 확인
gh run list --workflow=daily_generate.yml
```

## 환경변수 전체 목록

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `OPENAI_API_KEY` | (필수) | OpenAI API 인증 키 |
| `MODEL_NAME` | `gpt-4` | 사용할 LLM 모델 |
| `POSTS_DIR` | `./posts` | 포스트 저장 디렉토리 |
| `SITE_DIR` | `./site` | 빌드 출력 디렉토리 |
| `TEMPLATE_DIR` | `./templates` | HTML 템플릿 디렉토리 |
| `SITE_TITLE` | `Tech Blog` | 사이트 제목 |
| `SITE_URL` | `https://minjungsung.github.io/medium` | 사이트 URL |
| `POSTS_PER_PAGE` | `10` | 인덱스 페이지당 포스트 수 |
| `LANGUAGE` | `en` | 포스트 작성 언어 |

## 커스터마이징

### 새 카테고리 추가

`src/generator/topic.py`의 카테고리 목록에 새 카테고리를 추가할 수 있습니다.

### 템플릿 수정

`templates/` 디렉토리의 HTML 파일을 수정하여 사이트 디자인을 변경할 수 있습니다.

### 포스트 생성 스케줄 변경

`.github/workflows/daily_generate.yml`의 cron 표현식을 수정합니다:

```yaml
on:
  schedule:
    # 매일 오전 9시 KST (UTC 00:00)
    - cron: '0 0 * * *'
    
    # 주중만 (월-금)
    # - cron: '0 0 * * 1-5'
    
    # 일주일에 2번 (월, 목)
    # - cron: '0 0 * * 1,4'
```

## 문제 해결

| 문제 | 해결 방법 |
|------|----------|
| API rate limit | OpenAI 사용량 확인, 재시도 로직 추가 |
| 워크플로우 실패 | Actions 탭에서 로그 확인 |
| Pages 배포 안 됨 | Pages 설정에서 source 확인, 워크플로우 권한 확인 |
| 포스트 품질 저하 | 프롬프트 수정 (`src/generator/writer.py`) |
| 빌드 오류 | `python scripts/publish.py` 로컬 실행으로 디버그 |
