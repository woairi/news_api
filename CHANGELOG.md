# 변경 내역

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
