# 변경 내역

## [2026-01-05] - 저장소 이전 및 보안 개선

### 🔒 보안
- **Git 히스토리 정리**: `.env` 파일을 모든 커밋 히스토리에서 완전히 제거하여 API 키 노출 방지
- **환경변수 보호**: `.gitignore`에 `.env` 파일이 포함되어 있으며, Git에서 추적되지 않도록 설정됨

### 🚀 기능 추가
- **Fluent Design 테마**: Microsoft Fluent Design 스타일의 새로운 UI 테마 추가
- **Glassmorphism 테마**: 현대적인 glassmorphism 스타일의 UI 테마 추가
- **Material Design 3**: 프론트엔드를 Material Design 3로 전면 개편 및 SPA 아키텍처 적용
- **AI Provider 선택**: Gemini 또는 Perplexity AI 중 선택 가능한 요약 엔진 추가

### 🔧 기타
- **저장소 이전**: `woairi/ai_news_bot` → `woairi/news_api`로 GitHub 저장소 이전
- **프론트엔드 정적 파일**: CSS 및 HTML 스타일 업데이트
- **뉴스 키워드**: 검색 키워드 및 AI 제공자 설정 업데이트

### ⚠️ 주의사항
- 저장소 URL이 변경되었습니다: `https://github.com/woairi/news_api.git`
- 기존 저장소를 사용하던 경우 원격 저장소 URL을 업데이트해야 합니다:
  ```bash
  git remote set-url origin https://github.com/woairi/news_api.git
  ```

## [2025-11-04] - DatacenterDynamics 요약 재도입

### 🚀 기능 추가
- `send_ai_news.py`: DatacenterDynamics 주요 채널 크롤링, 메타데이터 파싱, Gemini 기반 요약 및 카테고리 저장/발송 로직을 추가했습니다.
- `web_app.py`: 요약 카테고리 탭 UI, API 파라미터, 관리자 모듈 연동 등 데이터센터 요약 조회 기능을 확장했습니다.

### 🐛 버그 수정
- `web_app.py`: 초기 로딩 시 최신 요약이 표시되지 않던 문제와 줄바꿈 치환 정규식 오류를 수정했습니다.

### 🛠️ 기타
- `requirements.txt`: `beautifulsoup4` 의존성을 추가했습니다.
- `README.md`: DatacenterDynamics 요약 기능과 개선된 UI 정보를 주요 기능 항목에 반영했습니다.
- 웹 메인 레이아웃을 요약/날짜 패널 2열 구조로 정리하고 상태 카드 스타일을 재조정했습니다.
- 최근 일주일 요약 목록을 2열 격자형 스크롤로 정돈해 날짜 탐색을 단순화했습니다.

### 🐛 버그 수정
- DatacenterDynamics 요약을 기사 발행 날짜로 저장하도록 수정해 하루 전 기사도 정상 노출되도록 했습니다.
- 상태 패널과 최신 실행 시각을 한국 표준시(KST)로 표시해 운영 시간을 직관적으로 확인할 수 있습니다.

## [2025-11-04] - 롤백: 데이터센터 뉴스 요약 기능 추가 시도

### 롤백
- 데이터센터 뉴스 요약 기능 추가 시도 후 발생한 오류로 인해 관련 코드 변경 사항을 롤백했습니다.
- `send_ai_news.py`: `fetch_datacenter_news` 함수, `generate_summary` 및 `save_summary_to_db` 함수의 `news_type` 관련 변경 사항, `run_news_bot` 함수의 데이터센터 뉴스 처리 로직이 롤백되었습니다.
- `web_app.py`: 웹 인터페이스의 탭 구조, `get_summary` 및 `get_all_dates` 함수의 `summary_type` 관련 변경 사항, `parseSummary` JavaScript 함수 수정 사항이 롤백되었습니다.

### 알려진 문제
- 데이터센터 뉴스 요약 기능 추가 과정에서 `SyntaxError` 및 `sqlite3.OperationalError`가 발생했습니다.
- 현재 버전은 기능 추가 이전 상태로 복원되었습니다.

## v1.1.0 (2025-10-28)

### 🚀 기능 추가

- 없음

### 🐛 버그 수정

- **텔레그램**: 메시지 길이 제한(4096자) 초과 시 여러 메시지로 분할 전송하여 문제 해결
- **텔레그램**: 메시지 전송 타임아웃을 30초에서 60초로 늘려 안정성 향상

### 📝 문서

- `README.md`: 설치 및 실행 방법 개선, 변경 내역 섹션 추가
- `CHANGELOG.md`: 프로젝트 변경 내역 추적을 위한 파일 생성

### 🔧 기타

- 없음
