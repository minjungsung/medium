# Medium — AI-Powered Tech Blog Wiki

> GitHub Actions로 기술 블로그를 자동 생성하고 GitHub Pages로 배포하는 자동화 파이프라인

## 프로젝트 개요

**Medium**은 AI를 활용하여 기술 블로그 포스트를 자동으로 생성하고, Markdown에서 HTML로 변환한 후 GitHub Pages로 배포하는 완전 자동화된 콘텐츠 파이프라인입니다.

매일 정해진 시간에 GitHub Actions 워크플로우가 실행되어 새로운 기술 포스트를 작성하고, 이를 정적 사이트로 빌드하여 자동 배포합니다.

### 핵심 기능
- **AI 포스트 생성**: LLM을 활용한 기술 블로그 포스트 자동 작성
- **자동 퍼블리싱**: Markdown 작성에서 HTML 변환, 배포까지 완전 자동화
- **GitHub Pages 배포**: 정적 사이트로 빌드하여 GitHub Pages에 무료 호스팅
- **스케줄 기반**: cron 스케줄로 매일 자동 실행
- **주제 다양성**: 다양한 기술 주제를 커버하는 지능적 주제 선정

## 기술 스택

| 카테고리 | 기술 |
|---------|------|
| 언어 | Python 3.10+ |
| 콘텐츠 생성 | OpenAI API / LLM |
| 마크업 | Markdown |
| 정적 사이트 | Custom HTML Builder |
| CI/CD | GitHub Actions |
| 호스팅 | GitHub Pages |
| 버전 관리 | Git |

## 프로젝트 구조

```
medium/
├── .github/
│   └── workflows/
│       ├── daily_generate.yml    # 매일 포스트 생성 워크플로우
│       ├── daily_publish.yml     # 매일 퍼블리싱 워크플로우
│       └── deploy_pages.yml      # GitHub Pages 배포 워크플로우
├── posts/                        # Markdown 포스트 파일
│   ├── 2024-01-15-topic.md
│   └── ...
├── scripts/                      # 유틸리티 스크립트
│   ├── generate.py               # 포스트 생성 스크립트
│   └── publish.py                # HTML 변환 스크립트
├── src/                          # 핵심 소스 코드
│   ├── generator/                # 콘텐츠 생성기
│   ├── builder/                  # 사이트 빌더
│   └── utils/                    # 유틸리티
├── site/                         # 빌드된 정적 사이트 (HTML)
│   ├── index.html
│   ├── posts/
│   └── assets/
├── templates/                    # HTML 템플릿
├── requirements.txt
└── README.md
```

## Wiki 목차

| 페이지 | 설명 |
|--------|------|
| [Architecture](Architecture) | 콘텐츠 파이프라인 아키텍처, 시스템 다이어그램 |
| [Services](Services) | 각 컴포넌트 상세 설명 (생성기, 퍼블리셔, 빌더, Actions) |
| [Setup Guide](Setup-Guide) | 로컬 실행, GitHub Actions 설정, 환경변수 |
| [Content Pipeline](Content-Pipeline) | 포스트 생성 주기, 주제 선정 로직 |

## 빠른 시작

```bash
# 리포지토리 클론
git clone https://github.com/minjungsung/medium.git
cd medium

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
export OPENAI_API_KEY="your-api-key"

# 포스트 생성
python scripts/generate.py

# 사이트 빌드
python scripts/publish.py

# 로컬 미리보기
python -m http.server 8080 --directory site/
```

자세한 설정 방법은 [Setup Guide](Setup-Guide)를 참조하세요.
